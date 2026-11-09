"""The order brain: keeps the cart, follows the rules, decides the reply.

Golden rule: an order stays DRAFT until the customer says an explicit "yes"
AFTER hearing the read-back and completing serving/payment steps. Only then
it becomes CONFIRMED (and will show on the kitchen dashboard). Prices ALWAYS
come from the database.
"""
import urllib.parse
from app import config
from app.db import get_db
from app.services import menu_matcher as mm
from app.services import nlu
from app.services.texts import join_list, say

MAX_QTY = 20

# Remembers what the agent just asked each customer (kept in memory).
#   awaiting: None | "more" | "confirm" | "clarify" | "upsell" | "where" | "table" | "name" | "phone" | "payment" | "upi_confirm"
#   serving:  dine-in / takeaway and table number, once the customer has told us
#   ready:    True only AFTER the customer said "yes" and we are collecting final details (where/table/name/phone/payment)
SESSIONS = {}

def _state(session_id):
    return SESSIONS.setdefault(session_id, {
        "awaiting": None, "pending": None, "last_item": None, "last_reply": "", "upsold": False,
        "serving": {"type": None, "table": None}, "ready": False,
        "customer_name": None, "customer_phone": None, "payment_mode": None, "upi_paid": False})


# ---------- small database helpers ----------

def _draft_order_id(db, session_id, language, customer_id=None, channel="web"):
    row = db.execute(
        "SELECT id FROM orders WHERE session_id = ? AND status = 'DRAFT' ORDER BY id DESC LIMIT 1",
        (session_id,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO orders (session_id, language, customer_id, channel) VALUES (?, ?, ?, ?)",
                     (session_id, language, customer_id, channel))
    db.commit()
    return cur.lastrowid


def _lines(db, order_id):
    rows = db.execute(
        "SELECT oi.id AS line_id, oi.menu_item_id, oi.quantity, oi.unit_price, oi.notes,"
        " m.name_en, m.name_kn, m.name_hi"
        " FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id"
        " WHERE oi.order_id = ? ORDER BY oi.id", (order_id,)).fetchall()
    return [dict(r) for r in rows]


def _total(lines):
    return sum(l["quantity"] * l["unit_price"] for l in lines)


def _save_total(db, order_id):
    total = _total(_lines(db, order_id))
    db.execute("UPDATE orders SET total = ? WHERE id = ?", (total, order_id))
    db.commit()
    return total


def _name(row, lang):
    "Dish name in the customer's language (falls back to English)."
    if lang == "hi" and row.get("name_hi"):
        return row["name_hi"]
    if lang == "kn" and row.get("name_kn"):
        return row["name_kn"]
    return row["name_en"]


def _phrase(pairs, lang):
    "[(row, qty), ...] -> '2 Masala Dosa and 1 Filter Coffee'."
    return join_list(lang, [f"{qty} {_name(row, lang)}" for row, qty in pairs])


def _cart_phrase(lines, lang):
    return _phrase([(l, l["quantity"]) for l in lines], lang)


def _find_line(lines, item_id):
    return next((l for l in lines if l["menu_item_id"] == item_id), None)


def _add(db, order_id, item, qty, note=""):
    line = _find_line(_lines(db, order_id), item["id"])
    if line:
        new_note = (line["notes"] + "; " + note).strip("; ") if note else line["notes"]
        db.execute("UPDATE order_items SET quantity = quantity + ?, notes = ? WHERE id = ?",
                   (qty, new_note, line["line_id"]))
    else:
        db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes)"
                   " VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))
    db.commit()


def _attach_notes(db, order_id, notes, fallback_item_id):
    "Save notes like 'no onion' on the right dish. Returns True if any was saved."
    saved = False
    for note in notes:
        target = note["item_id"] or fallback_item_id
        line = _find_line(_lines(db, order_id), target) if target else None
        if line:
            new_note = (line["notes"] + "; " + note["text"]).strip("; ")
            db.execute("UPDATE order_items SET notes = ? WHERE id = ?", (new_note, line["line_id"]))
            db.commit()
            saved = True
    return saved


def _pick_upsell(db, menu, lines):
    """One drink to suggest: the best-selling available drink, if the cart has no drink yet."""
    by_id = {m["id"]: m for m in menu}
    if any(by_id[l["menu_item_id"]]["category"] == "Drinks" for l in lines):
        return None
    row = db.execute(
        """SELECT m.id, COALESCE((SELECT SUM(oi.quantity) FROM order_items oi
                                   JOIN orders o ON o.id = oi.order_id
                                   WHERE oi.menu_item_id = m.id AND o.confirmed_at IS NOT NULL
                                     AND o.status != 'CANCELLED'), 0) AS sold
           FROM menu_items m WHERE m.category = 'Drinks' AND m.available = 1
           ORDER BY sold DESC, m.id LIMIT 1""").fetchone()
    return by_id[row["id"]] if row else None


def _alternatives(menu, item, lang):
    same = [m for m in menu if m["category"] == item["category"] and m["available"] and m["id"] != item["id"]]
    if not same:
        return ""
    names = join_list(lang, [_name(m, lang) for m in same[:2]])
    return " " + say(lang, "alternatives", alts=names)


def handle_turn(session_id, text, language_code="en-IN", customer_id=None, channel="web",
                serving=None, customer_name=None, customer_phone=None, payment_mode=None):
    "customer_id: who is ordering (browser id or phone number) - used for 'same as last time'."
    "serving: optional {\"type\": \"dine-in\"|\"takeaway\", \"table\": \"5\"} already known (QR code / phone call)."
    lang = (language_code or "en").split("-")[0]
    if lang not in ("en", "hi", "kn"):
        lang = "en"
    db = get_db()
    menu = [dict(r) for r in db.execute("SELECT * FROM menu_items ORDER BY id")]
    by_id = {m["id"]: m for m in menu}
    st = _state(session_id)
    order_id = _draft_order_id(db, session_id, language_code, customer_id, channel)
    lines_before = _lines(db, order_id)

    # Sync any explicit profile data passed from client
    if customer_name and not st.get("customer_name"):
        st["customer_name"] = str(customer_name).strip()[:50]
        db.execute("UPDATE orders SET customer_name = ? WHERE id = ?", (st["customer_name"], order_id))
        db.commit()
    if customer_phone and not st.get("customer_phone"):
        st["customer_phone"] = str(customer_phone).strip()[:15]
        db.execute("UPDATE orders SET customer_phone = ? WHERE id = ?", (st["customer_phone"], order_id))
        db.commit()
    if payment_mode and not st.get("payment_mode"):
        st["payment_mode"] = str(payment_mode).strip().lower()
        db.execute("UPDATE orders SET payment_mode = ? WHERE id = ?", (st["payment_mode"], order_id))
        db.commit()

    context = {"awaiting": st["awaiting"],
               "cart": [{"quantity": l["quantity"], "name": l["name_en"]} for l in lines_before]}
    awaiting = st["awaiting"]
    if serving:
        # Only a default: what the customer actually SAID ("takeaway", "table 5") wins,
        # otherwise the web form would reset it on every turn.
        if serving.get("type") and not st["serving"]["type"]:
            st["serving"]["type"] = serving["type"]
        if serving.get("table") and not st["serving"]["table"] and st["serving"]["type"] != "takeaway":
            st["serving"]["table"] = serving["table"]

    # Did the customer say "takeaway" / "dine in" / "table 5"?
    clean_text = mm.clean(text)
    rules_intent = nlu.parse_rules(text, menu, lang)["intent"]
    hit = nlu.detect_serving(clean_text, lang, awaiting, allow_bare=(rules_intent == "unknown"))
    if hit:
        if hit["type"] == "takeaway":
            st["serving"] = {"type": "takeaway", "table": None}
        else:
            st["serving"] = {"type": "dine-in", "table": hit["table"] or st["serving"]["table"]}

    # Check for phone number in text
    phone_hit = nlu.detect_phone(text, lang)
    if phone_hit and not st.get("customer_phone"):
        st["customer_phone"] = phone_hit
        db.execute("UPDATE orders SET customer_phone = ? WHERE id = ?", (phone_hit, order_id))
        db.commit()

    # Check for payment mode in text
    pay_hit = nlu.detect_payment(text)
    if pay_hit:
        st["payment_mode"] = pay_hit
        db.execute("UPDATE orders SET payment_mode = ? WHERE id = ?", (pay_hit, order_id))
        db.commit()

    if hit and rules_intent in ("unknown", "confirm", "deny", "greet", "done"):
        parsed = {"intent": "serving", "items": [], "ambiguous": [], "notes": [],
                  "bare_quantity": None, "filter": None, "source": "rules"}
    else:
        parsed = nlu.parse(text, menu, lang, context)
    intent = parsed["intent"]
    confirmed = False

    # The customer is answering "which one?" -> reuse the quantity they gave before.
    if awaiting == "clarify" and st.get("pending") and intent == "order":
        ids = st["pending"]["candidates"]
        if len(parsed["items"]) == 1 and parsed["items"][0]["item_id"] in ids and not parsed["items"][0]["explicit"]:
            parsed["items"][0]["quantity"] = st["pending"]["quantity"]
    if awaiting == "clarify" and intent not in ("order", "unknown"):
        st["pending"] = None

    parts = []          # sentences, joined at the end
    new_awaiting = None

    def read_back():
        lines = _lines(db, order_id)
        return say(lang, "cart_line", cart=_cart_phrase(lines, lang), total=_total(lines)) + " " + say(lang, "q_confirm")

    def serving_missing():
        sv = st["serving"]
        if sv["type"] is None:
            return "where"
        if sv["type"] == "dine-in" and not sv["table"]:
            return "table"
        return None

    def serving_sentence():
        sv = st["serving"]
        if sv["type"] == "takeaway":
            return say(lang, "serving_take")
        if sv["table"]:
            return say(lang, "serving_dine", table=sv["table"])
        return say(lang, "serving_dine_nt")


    def try_place():
        nonlocal confirmed
        lines_now = _lines(db, order_id)
        if not lines_now:
            parts.append(say(lang, "empty_ask"))
            return None

        gone = []
        for l in lines_now:                     # last safety check: is everything still in stock?
            if not by_id[l["menu_item_id"]]["available"]:
                gone.append(l)
                db.execute("DELETE FROM order_items WHERE id = ?", (l["line_id"],))
        db.commit()
        if gone:
            for l in gone:
                parts.append(say(lang, "stock_removed", name=_name(l, lang)))
            _save_total(db, order_id)
            if _lines(db, order_id):
                parts.append(read_back())
                return "confirm"
            parts.append(say(lang, "empty_ask"))
            return None

        # 1. Customer Name
        if not st.get("customer_name"):
            parts.append(say(lang, "ask_name"))
            st["ready"] = True
            return "name"

        # 2. Serving (Dine-in / Takeaway / Table)
        missing = serving_missing()
        if missing:
            parts.append(say(lang, "ask_where" if missing == "where" else "ask_table"))
            st["ready"] = True
            return missing

        # 3. Customer Phone
        if not st.get("customer_phone"):
            parts.append(say(lang, "ask_phone"))
            st["ready"] = True
            return "phone"

        # 4. Payment Mode (Cash vs UPI)
        if not st.get("payment_mode"):
            parts.append(say(lang, "ask_payment"))
            st["ready"] = True
            return "payment"

        # 5. If UPI, verify scanning / payment confirmation
        total = _save_total(db, order_id)
        if st.get("payment_mode") == "upi" and not st.get("upi_paid"):
            if wants_checkout:              # "confirm" / "I have paid, place order" button
                st["upi_paid"] = True
            else:
                parts.append(say(lang, "pay_upi_qr", total=total))
                st["ready"] = True
                return "upi_confirm"

        # All requirements satisfied. Place the order now.
        # Cash orders go to AWAITING_CASH (no confirmed_at) so the kitchen must
        # collect cash and click "Cash Collected" before they start preparing.
        # UPI orders are confirmed immediately — payment was already received.
        sv = st["serving"]
        is_cash = st.get("payment_mode") == "cash"
        if is_cash:
            db.execute("UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no = ?,"
                       " customer_id = ?, channel = ?, customer_name = ?, customer_phone = ?,"
                       " payment_mode = ? WHERE id = ?",
                       (language_code, sv["type"], sv["table"], customer_id, channel,
                        st.get("customer_name"), st.get("customer_phone"), st.get("payment_mode"), order_id))
            parts.append(say(lang, "cash_submitted", id=order_id, total=total) + " " + serving_sentence())
        else:
            db.execute("UPDATE orders SET status = 'CONFIRMED', language = ?, order_type = ?, table_no = ?,"
                       " customer_id = ?, channel = ?, customer_name = ?, customer_phone = ?,"
                       " payment_mode = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
                       (language_code, sv["type"], sv["table"], customer_id, channel,
                        st.get("customer_name"), st.get("customer_phone"), st.get("payment_mode"), order_id))
            parts.append(say(lang, "confirmed", id=order_id, total=total) + " " + serving_sentence())
        db.commit()
        confirmed = True
        return None

    wants_checkout = intent == "confirm" and mm.contains(mm.clean(text), nlu.PLACE_ORDER)

    # Is the customer telling us their name? ("my name is Ravi" at any time, or just "Ravi" when asked.)
    name_answer = None
    if not hit and not phone_hit and not pay_hit and intent in ("unknown", "greet"):
        name_answer = nlu.explicit_name(text)
        if not name_answer and awaiting == "name" and intent == "unknown":
            name_answer = nlu.extract_name(text)
        if name_answer and len(name_answer) < 2:
            name_answer = None

    # State handler: customer gave their name
    if name_answer:
        st["customer_name"] = name_answer
        db.execute("UPDATE orders SET customer_name = ? WHERE id = ?", (name_answer, order_id))
        db.commit()
        if st["ready"]:
            new_awaiting = try_place()      # we were collecting checkout details
        else:
            parts.append(say(lang, "greet_named", name=name_answer))
            new_awaiting = awaiting if awaiting not in (None, "name") else None

    # Asked for the name but got "yes" / "hello" / silence-like noise: ask again.
    # (Orders, questions and cancel fall through to the normal handlers below.)
    elif awaiting == "name" and intent in ("unknown", "greet", "confirm", "deny", "done"):
        parts.append(say(lang, "ask_name"))
        new_awaiting = "name"

    # State handler: awaiting phone
    elif awaiting == "phone":
        phone = nlu.detect_phone(text, lang)
        if phone:
            st["customer_phone"] = phone
            db.execute("UPDATE orders SET customer_phone = ? WHERE id = ?", (phone, order_id))
            db.commit()
            new_awaiting = try_place()
        elif intent == "cancel":
            db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
            db.commit()
            parts.append(say(lang, "cancelled"))
        else:
            parts.append(say(lang, "ask_phone_retry"))
            new_awaiting = "phone"

    # State handler: awaiting payment selection
    elif awaiting == "payment":
        mode = nlu.detect_payment(text)
        if mode:
            st["payment_mode"] = mode
            db.execute("UPDATE orders SET payment_mode = ? WHERE id = ?", (mode, order_id))
            db.commit()
            if mode == "cash":
                new_awaiting = try_place()
            else:  # upi
                total = _save_total(db, order_id)
                parts.append(say(lang, "pay_upi_qr", total=total))
                st["ready"] = True
                new_awaiting = "upi_confirm"
        elif intent == "cancel":
            db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
            db.commit()
            parts.append(say(lang, "cancelled"))
        else:
            parts.append(say(lang, "ask_payment"))
            new_awaiting = "payment"

    # State handler: awaiting UPI payment confirmation
    elif awaiting == "upi_confirm":
        clean = mm.clean(text)
        if nlu.detect_payment(text) == "cash":
            st["payment_mode"] = "cash"
            db.execute("UPDATE orders SET payment_mode = 'cash' WHERE id = ?", (order_id,))
            db.commit()
            new_awaiting = try_place()
        elif intent in ("confirm", "done") or "paid" in clean or "done" in clean or "success" in clean or "confirm" in clean:
            st["upi_paid"] = True
            new_awaiting = try_place()
        elif intent == "cancel":
            db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
            db.commit()
            parts.append(say(lang, "cancelled"))
        else:
            total = _save_total(db, order_id)
            parts.append(say(lang, "pay_upi_qr", total=total))
            new_awaiting = "upi_confirm"

    elif intent == "serving":
        said_yes = awaiting == "confirm" and rules_intent == "confirm"      # "yes, takeaway"
        if (st["ready"] and awaiting in ("where", "table")) or said_yes:
            new_awaiting = try_place()      # this was the missing detail
        else:
            parts.append(say(lang, "note", note=serving_sentence().rstrip("。.।")))
            if awaiting == "name":
                parts.append(say(lang, "ask_name"))
            new_awaiting = awaiting

    elif awaiting in ("where", "table") and intent in ("confirm", "deny", "unknown", "greet", "done"):
        parts.append(say(lang, "ask_where" if awaiting == "where" else "ask_table"))
        new_awaiting = awaiting

    elif intent == "reorder":
        last = db.execute(
            "SELECT id FROM orders WHERE customer_id = ? AND confirmed_at IS NOT NULL"
            " AND status != 'CANCELLED' ORDER BY id DESC LIMIT 1", (customer_id,)).fetchone() if customer_id else None
        if lines_before:
            parts.append(say(lang, "reorder_busy"))
            new_awaiting = awaiting
        elif not last:
            parts.append(say(lang, "reorder_none"))
        else:
            added, skipped = [], []
            for l in _lines(db, last["id"]):
                item = by_id.get(l["menu_item_id"])
                if item and item["available"]:
                    _add(db, order_id, item, min(l["quantity"], MAX_QTY), l["notes"])
                    st["last_item"] = item["id"]
                    added.append((item, min(l["quantity"], MAX_QTY)))
                else:
                    skipped.append(l)
            total = _save_total(db, order_id)
            if skipped:
                parts.append(say(lang, "reorder_skipped", names=join_list(lang, [_name(l, lang) for l in skipped])))
            if added:
                parts.append(say(lang, "reorder_ok", cart=_cart_phrase(_lines(db, order_id), lang), total=total))
                parts.append(say(lang, "q_confirm"))
                new_awaiting = "confirm"
            else:
                parts.append(say(lang, "empty_ask"))
                new_awaiting = awaiting

    elif awaiting == "upsell" and st["pending"] and intent in ("confirm", "deny") and not wants_checkout:
        suggestion = by_id.get(st["pending"]["item_id"])
        st["pending"] = None
        if intent == "confirm" and suggestion and suggestion["available"]:
            _add(db, order_id, suggestion, 1)
            st["last_item"] = suggestion["id"]
            total = _save_total(db, order_id)
            parts.append(say(lang, "added", added=_phrase([(suggestion, 1)], lang), total=total))
        else:
            parts.append(say(lang, "no_problem"))
        parts.append(say(lang, "q_more"))
        new_awaiting = "more"

    elif intent in ("order", "modify") and not (intent == "modify" and parsed["bare_quantity"] is not None and not parsed["items"]):
        added, changed, problems = [], [], []
        for it in parsed["items"]:
            item = by_id[it["item_id"]]
            qty = it["quantity"]
            line = _find_line(_lines(db, order_id), item["id"])
            if not item["available"]:
                problems.append(say(lang, "unavailable", name=_name(item, lang)) + _alternatives(menu, item, lang))
                continue
            if intent == "modify" and line:
                if qty > MAX_QTY:
                    problems.append(say(lang, "too_many", max=MAX_QTY))
                    continue
                db.execute("UPDATE order_items SET quantity = ? WHERE id = ?", (qty, line["line_id"]))
                db.commit()
                changed.append((item, qty))
            else:
                if (line["quantity"] if line else 0) + qty > MAX_QTY:
                    problems.append(say(lang, "too_many", max=MAX_QTY))
                    continue
                _add(db, order_id, item, qty)
                added.append((item, qty))
            st["last_item"] = item["id"]
        _attach_notes(db, order_id, parsed["notes"], st["last_item"])
        total = _save_total(db, order_id)
        parts += problems
        ask = None
        if parsed["ambiguous"]:
            amb = parsed["ambiguous"][0]
            options = join_list(lang, [_name(by_id[i], lang) for i in amb["candidates"] if by_id[i]["available"]]
                                or [_name(by_id[i], lang) for i in amb["candidates"]], "or")
            ask = say(lang, "ask_which", options=options)
            st["pending"] = {"candidates": amb["candidates"], "quantity": amb["quantity"]}
            new_awaiting = "clarify"
        if changed:
            item, qty = changed[-1]
            parts.append(say(lang, "modified", qty=qty, name=_name(item, lang), total=total))
            if not ask:
                parts.append(say(lang, "q_confirm"))
                new_awaiting = "confirm"
        if added:
            if not lines_before and not ask and not changed:
                parts.append(say(lang, "ordered", cart=_cart_phrase(_lines(db, order_id), lang)))
                suggestion = None if st["upsold"] else _pick_upsell(db, menu, _lines(db, order_id))
                if suggestion:      # suggest ONE drink, once per customer
                    parts.append(say(lang, "upsell", name=_name(suggestion, lang), price=suggestion["price"]))
                    st["pending"] = {"item_id": suggestion["id"]}
                    st["upsold"] = True
                    new_awaiting = "upsell"
                else:
                    parts.append(say(lang, "q_more"))
                    new_awaiting = "more"
            else:
                parts.append(say(lang, "added", added=_phrase(added, lang), total=total))
                if not ask:
                    parts.append(say(lang, "q_confirm"))
                    new_awaiting = "confirm"
        if ask:
            parts.append(ask)
        if not parts:
            parts.append(say(lang, "unknown"))
        if not added and not changed and not ask:
            new_awaiting = awaiting if awaiting in ("more", "confirm", "upsell") else None

    elif intent == "modify":   # "make it three" -> applies to the last dish
        lines = _lines(db, order_id)
        line = _find_line(lines, st.get("last_item")) if st.get("last_item") else None
        qty = parsed.get("bare_quantity")
        if not line:
            parts.append(say(lang, "empty_ask"))
        elif qty > MAX_QTY:
            parts.append(say(lang, "too_many", max=MAX_QTY))
        else:
            db.execute("UPDATE order_items SET quantity = ? WHERE id = ?", (qty, line["line_id"]))
            db.commit()
            total = _total(_lines(db, order_id))
            parts.append(say(lang, "modified", qty=qty, name=_name(line, lang), total=total))
            parts.append(say(lang, "q_confirm"))
            new_awaiting = "confirm"

    elif intent == "remove":
        removed, problems = [], []
        targets = list(parsed["items"])
        for amb in parsed.get("ambiguous", []):
            in_cart = [l for l in _lines(db, order_id) if l["menu_item_id"] in amb["candidates"]]
            if len(in_cart) == 1:
                targets.append({"item_id": in_cart[0]["menu_item_id"], "quantity": amb["quantity"], "explicit": amb["explicit"]})
            elif len(in_cart) > 1:
                names = join_list(lang, [_name(l, lang) for l in in_cart], "or")
                problems.append(say(lang, "ask_which", options=names))
            else:
                problems.append(say(lang, "unknown"))
        for it in targets:
            item = by_id[it["item_id"]]
            line = _find_line(_lines(db, order_id), item["id"])
            if not line:
                problems.append(say(lang, "not_in_cart", name=_name(item, lang)))
            elif it.get("explicit") and it["quantity"] < line["quantity"]:
                db.execute("UPDATE order_items SET quantity = quantity - ? WHERE id = ?", (it["quantity"], line["line_id"]))
                removed.append((item, it["quantity"]))
            else:
                db.execute("DELETE FROM order_items WHERE id = ?", (line["line_id"],))
                removed.append((item, line["quantity"]))
        db.commit()
        total = _total(_lines(db, order_id))
        parts += problems
        if removed:
            if _lines(db, order_id):
                parts.append(say(lang, "removed", removed=_cart_phrase(_lines(db, order_id), lang), total=total))
                parts.append(say(lang, "q_confirm"))
                new_awaiting = "confirm"
            else:
                parts.append(say(lang, "removed_empty", removed=_cart_phrase([], lang)))
        elif not parts:
            parts.append(say(lang, "unknown"))

    elif intent == "total":
        lines = _lines(db, order_id)
        if lines:
            parts.append(say(lang, "cart_line", cart=_cart_phrase(lines, lang), total=_total(lines)))
            new_awaiting = awaiting
        else:
            parts.append(say(lang, "empty_ask"))
            new_awaiting = None

    elif intent == "done" or (intent == "deny" and awaiting == "more"):
        parts.append(read_back() if lines_before else say(lang, "empty_ask"))
        new_awaiting = "confirm" if lines_before else None

    elif intent == "confirm":
        if not lines_before:
            parts.append(say(lang, "empty_ask"))
        elif awaiting != "confirm" and not wants_checkout:
            # They have not heard the read-back yet, so we read it back first.
            parts.append(read_back())
            new_awaiting = "confirm"
        else:
            new_awaiting = try_place()

    elif intent == "deny":
        parts.append(say(lang, "change") if lines_before else say(lang, "empty_ask"))

    elif intent == "cancel":
        db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
        db.commit()
        parts.append(say(lang, "cancelled"))

    elif intent == "menu":
        names = [_name(m, lang) for m in menu if m["available"]][:8]
        parts.append(say(lang, "menu", list=join_list(lang, names)))
        new_awaiting = awaiting

    elif intent == "filter":
        f = parsed.get("filter") or {}
        options = [m for m in menu if m["available"]]
        if f.get("category"):
            options = [m for m in options if m["category"] == f["category"]]
        if f.get("veg") is True:
            options = [m for m in options if m["veg"]]
        elif f.get("veg") is False:
            options = [m for m in options if not m["veg"]]
        if f.get("max_price"):
            options = [m for m in options if m["price"] <= f["max_price"]]
        options.sort(key=lambda m: m["price"])
        if f.get("cheap") and not f.get("max_price"):
            options = options[:3]
        if options:
            listing = join_list(lang, [say(lang, "priced", name=_name(m, lang), price=m["price"]) for m in options[:6]])
            parts.append(say(lang, "filter_result", list=listing))
        else:
            parts.append(say(lang, "filter_none"))
        new_awaiting = awaiting

    elif intent == "price":
        for it in parsed["items"]:
            item = by_id[it["item_id"]]
            parts.append(say(lang, "price", name=_name(item, lang), price=item["price"]))
        new_awaiting = awaiting

    elif intent == "availability":
        for it in parsed["items"]:
            item = by_id[it["item_id"]]
            key = "avail_yes" if item["available"] else "avail_no"
            parts.append(say(lang, key, name=_name(item, lang)))
            if not item["available"]:
                # Simple alternatives
                avail_items = [m for m in menu if m["available"] and m["id"] != item["id"]]
                if avail_items:
                    alt_names = join_list(lang, [_name(m, lang) for m in avail_items[:2]])
                    parts[-1] += " " + say(lang, "alternatives", alts=alt_names)
            new_awaiting = awaiting

    elif intent == "note":
        if _attach_notes(db, order_id, parsed.get("notes", []), st.get("last_item")):
            parts.append(say(lang, "note", note="; ".join(n["text"] for n in parsed.get("notes", []))))
            new_awaiting = awaiting
        else:
            parts.append(say(lang, "empty_ask"))
            new_awaiting = awaiting

    elif intent == "repeat":
        parts.append(st["last_reply"] or say(lang, "unknown"))
        new_awaiting = awaiting

    elif intent == "greet":
        if not st.get("customer_name"):
            parts.append(say(lang, "ask_name"))
            new_awaiting = "name"
        else:
            parts.append(say(lang, "greet_named", name=st["customer_name"]))
            new_awaiting = awaiting

    else:
        parts.append(say(lang, "not_on_menu"))
        new_awaiting = awaiting

    reply = " ".join(p for p in parts if p)
    cart_lines = [] if intent == "cancel" else _lines(db, order_id)
    cart = {
        "items": [{"name": _name(l, lang), "quantity": l["quantity"], "unit_price": l["unit_price"],
                   "line_total": l["quantity"] * l["unit_price"], "notes": l["notes"]} for l in cart_lines],
        "total": _total(cart_lines),
    }

    # Generate UPI QR payload as soon as the cart has items so the customer
    # can scan at any time. The order stays DRAFT until they explicitly confirm.
    upi_payload = None
    if cart["total"] > 0:
        upi_id = config.UPI_ID
        payee = config.UPI_PAYEE_NAME
        amt = cart["total"]
        uri = f"upi://pay?pa={upi_id}&pn={urllib.parse.quote(payee)}&am={amt:.2f}&cu=INR&tn=Order_{order_id}"
        upi_payload = {
            "vpa": upi_id,
            "payee": payee,
            "amount": amt,
            "order_id": order_id,
            "uri": uri,
        }

    if confirmed:
        SESSIONS.pop(session_id, None)      # fresh start for the next order
    else:
        st["awaiting"] = new_awaiting
        if new_awaiting not in ("where", "table", "name", "phone", "payment", "upi_confirm"):
            st["ready"] = False
        if new_awaiting is not None and new_awaiting not in ("clarify", "upsell"):
            st["pending"] = None
        if intent != "repeat":
            st["last_reply"] = reply

    return {
        "reply": reply,
        "intent": intent,
        "source": parsed.get("source", "rules"),
        "awaiting": None if confirmed else (new_awaiting if new_awaiting is not None else None),
        "confirmed": confirmed,
        "order_id": order_id,
        "cart": cart,
        "customer_name": st.get("customer_name"),
        "customer_phone": st.get("customer_phone"),
        "payment_mode": st.get("payment_mode"),
        "serving": None if confirmed else dict(st["serving"]),
        "upi": upi_payload,
    }