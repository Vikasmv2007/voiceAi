"""Optional LLM "understanding" step (works with any OpenAI-compatible chat API).

The LLM only turns the customer's sentence into the SAME dictionary the rules
return (see nlu.py). It never decides prices, never confirms an order and never
talks to the kitchen: the order engine still does all of that. If the LLM is
off, slow, or returns something broken, we silently use the rules instead.
"""
import json
import re

import requests

from app import config

INTENTS = {"order", "remove", "modify", "confirm", "deny", "done", "cancel", "total", "menu",
           "price", "availability", "filter", "repeat", "greet", "note", "describe", "unknown"}

AWAITING = {
    None: "nothing in particular",
    "more": '"Would you like anything else?"',
    "confirm": '"Shall I confirm your order?"',
    "clarify": '"Which one would you like?" (the customer was vague about a dish)',
    "upsell": "whether the customer wants a suggested drink",
}

PROMPT = """You are the language-understanding module of a restaurant voice-ordering agent.
Convert ONE customer sentence into JSON. Reply with the JSON object only, no explanation.

The customer speaks English, Hindi, Kannada or a mix (Hinglish, Kanglish). The text comes from
speech recognition, so it may contain spelling mistakes.

MENU (id | English | Kannada | Hindi | price in rupees | available)
{menu}

CURRENT CART: {cart}
THE AGENT JUST ASKED: {awaiting}

JSON format:
{{"intent": "order", "items": [{{"item_id": 1, "quantity": 1, "explicit": false}}],
  "ambiguous": [{{"candidates": [1, 2], "quantity": 1}}],
  "notes": [{{"text": "no onion", "item_id": 1}}], "bare_quantity": null,
  "filter": null}}

intent must be one of: order, remove, modify, confirm, deny, done, cancel, total, menu, price,
availability, filter, repeat, greet, note, unknown.

Rules:
- item_id MUST be an id from the MENU. Never invent dishes or ids.
- quantity is a whole number, 1 if not said. "explicit" is true only if the customer said a number.
- order = add dishes. remove = take dishes out. modify = change how many of a dish ("make it 3").
  For "make it 3" with no dish named, use intent modify, items [] and bare_quantity 3.
- confirm = a clear yes. deny = a clear no. done = "that's all / nothing else". cancel = cancel the whole order.
- price = asking the price of a dish. availability = asking if a dish is available. total = asking the bill.
- describe = asking what a dish is, what is in it, or whether it is spicy.
- If a word could mean several dishes (only "dosa"), put it in "ambiguous" with the candidate ids and
  keep it out of "items".
- notes = special requests such as "no onion", "less spicy", "extra chutney" (item_id may be null).
- filter (only for intent "filter", e.g. "anything vegetarian under 50?"):
  {{"category": one of {categories} or null, "max_price": number | null, "veg": true | false | null}}
- If you cannot understand, use intent "unknown".

Examples:
"two masala dosa and one coffee" -> {{"intent":"order","items":[{{"item_id":1,"quantity":2,"explicit":true}},{{"item_id":11,"quantity":1,"explicit":true}}],"ambiguous":[],"notes":[],"bare_quantity":null,"filter":null}}
"ek idli bina pyaaz ke" -> {{"intent":"order","items":[{{"item_id":4,"quantity":1,"explicit":true}}],"ambiguous":[],"notes":[{{"text":"no onion","item_id":4}}],"bare_quantity":null,"filter":null}}
"yes please" -> {{"intent":"confirm","items":[],"ambiguous":[],"notes":[],"bare_quantity":null,"filter":null}}
"""


def configured():
    return bool(config.LLM_BASE_URL and config.LLM_MODEL and config.LLM_MODE != "off")


def wanted(rules_result, text):
    """Should we ask the LLM for this sentence?
    fallback = only when the rules are lost or the sentence is long and complicated.
    always   = every sentence (best for showing the LLM in your demo)."""
    if not configured():
        return False
    if config.LLM_MODE == "always":
        return True
    return rules_result["intent"] == "unknown" or len(text.split()) > 14


def _menu_text(menu):
    return "\n".join(
        f'{m["id"]} | {m["name_en"]} | {m["name_kn"] or ""} | {m["name_hi"] or ""} | {m["price"]} | '
        f'{"yes" if m["available"] else "NO"}' for m in menu)


def _cart_text(cart):
    return ", ".join(f'{c["quantity"]} x {c["name"]}' for c in cart) or "empty"


def _extract_json(content):
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S)   # reasoning models
    content = re.sub(r"```(?:json)?", "", content)
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON in the reply")
    return json.loads(content[start:end + 1])


def _whole(value, low, high, default=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


def validate(data, menu):
    """Check everything the LLM said against the real menu. Returns the
    standard dictionary, or None if it cannot be trusted."""
    ids = {m["id"] for m in menu}
    categories = {m["category"] for m in menu}
    intent = data.get("intent")
    if intent not in INTENTS:
        return None
    result = {"intent": intent, "items": [], "ambiguous": [], "notes": [],
              "bare_quantity": None, "filter": None}
    for it in data.get("items") or []:
        item_id = _whole(it.get("item_id"), 1, 10**9)
        if item_id in ids:
            qty = 1 if it.get("quantity") is None else _whole(it.get("quantity"), 1, 99)
            if qty is None:          # a made-up number like 5000: do not trust this answer at all
                return None
            result["items"].append({"item_id": item_id, "quantity": qty, "explicit": bool(it.get("explicit"))})
    for amb in data.get("ambiguous") or []:
        cands = [c for c in (_whole(x, 1, 10**9) for x in amb.get("candidates") or []) if c in ids]
        if len(cands) >= 2:
            result["ambiguous"].append({"candidates": cands, "quantity": _whole(amb.get("quantity"), 1, 99, 1),
                                        "explicit": bool(amb.get("explicit"))})
    for note in data.get("notes") or []:
        text = str(note.get("text") or "").strip()[:60]
        if text:
            owner = _whole(note.get("item_id"), 1, 10**9)
            result["notes"].append({"text": text, "item_id": owner if owner in ids else None})
    result["bare_quantity"] = _whole(data.get("bare_quantity"), 1, 99)
    flt = data.get("filter")
    if isinstance(flt, dict):
        result["filter"] = {
            "category": flt.get("category") if flt.get("category") in categories else None,
            "max_price": _whole(flt.get("max_price"), 1, 5000),
            "veg": flt.get("veg") if isinstance(flt.get("veg"), bool) else None,
            "cheap": False,
        }
    # An intent that needs dishes but has none is useless: let the rules try instead.
    if intent in ("order", "remove", "price", "availability", "describe") and not (result["items"] or result["ambiguous"]):
        return None
    if intent == "filter" and not result["filter"]:
        return None
    if intent == "modify" and not (result["items"] or result["bare_quantity"]):
        return None
    return result


def parse_with_llm(text, menu, lang, context):
    """Ask the LLM. Returns the standard dictionary, or None on ANY problem."""
    try:
        categories = " | ".join(json.dumps(c) for c in sorted({m["category"] for m in menu}))
        system = PROMPT.format(menu=_menu_text(menu), categories=categories, cart=_cart_text(context.get("cart", [])),
                               awaiting=AWAITING.get(context.get("awaiting"), "nothing in particular"))
        body = {"model": config.LLM_MODEL, "temperature": 0, "max_tokens": 500,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": f"Customer said: {text}"}]}
        if config.LLM_EXTRA:
            body.update(json.loads(config.LLM_EXTRA))
        headers = {"Content-Type": "application/json"}
        if config.LLM_API_KEY:
            headers["Authorization"] = "Bearer " + config.LLM_API_KEY
        r = requests.post(config.LLM_BASE_URL + "/chat/completions", headers=headers, json=body,
                          timeout=config.LLM_TIMEOUT)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return validate(_extract_json(content), menu)
    except Exception as e:      # slow, offline, rate-limited, broken JSON... fall back to rules
        print(f"[llm] falling back to rules: {type(e).__name__}: {str(e)[:120]}")
        return None
