"""Rule-based "understanding" of what the customer said.

parse() returns a plain dictionary, for example:
    {"intent": "order",
     "items": [{"item_id": 1, "quantity": 2, "explicit": True}],
     "ambiguous": [], "notes": [], "bare_quantity": None}

LATER, an LLM will return this exact same dictionary shape, so the rest of
the app (order engine, dashboard) will not need to change.
"""
import re

from app.services import llm
from app.services import menu_matcher as mm

CONFIRM = ["yes", "yeah", "yep", "yup", "ok", "okay", "sure", "confirm", "correct",
           "go ahead", "place the order", "proceed", "haan", "han", "haa", "ji",
           "theek hai", "thik hai", "हाँ", "हां", "जी", "ठीक है", "कन्फर्म", "पक्का",
           "ಹೌದು", "ಸರಿ", "ಹೂಂ", "ಕನ್ಫರ್ಮ್", "houdu", "sari"]
DENY = ["no", "nope", "nahi", "nahin", "नहीं", "नही", "ना", "ಇಲ್ಲ", "ಬೇಡ"]
DONE = ["that's all", "thats all", "that is all", "that is it", "that's it", "thats it",
        "nothing else", "nothing more", "no more", "that will be all", "bas", "बस",
        "ಅಷ್ಟೇ", "ಸಾಕು"]
REMOVE = ["remove", "delete", "take off", "take out", "don't want", "dont want", "cancel",
          "hata", "hatao", "nikal", "nikalo", "हटा", "हटाओ", "निकाल", "निकालो",
          "ಬೇಡ", "ತೆಗೆ", "ತೆಗೆದು", "beda"]
MODIFY = ["change", "make it", "make that", "instead", "update", "set it", "only",
          "badal", "बदल", "ಬದಲಾಯಿಸಿ", "ಬದಲು"]
CANCEL_ORDER = ["cancel order", "cancel my order", "cancel the order", "cancel everything",
                "cancel all", "start over", "clear order", "कैंसिल", "ऑर्डर रद्द", "ರದ್ದು"]
PRICE = ["price", "cost", "rate", "how much", "कीमत", "दाम", "ಬೆಲೆ", "ದರ"]
TOTAL = ["total", "bill", "amount", "kitna", "kitne", "कितना", "कितने", "कुल", "बिल",
         "ಎಷ್ಟು", "ಒಟ್ಟು", "ಬಿಲ್"]
MENU = ["menu", "what do you have", "what all", "what is available", "what's available",
        "whats available", "what can i order", "options", "recommend", "suggest",
        "popular", "special", "मेनू", "मेन्यू", "क्या है", "क्या मिलेगा", "ಮೆನು", "ಏನಿದೆ"]
AVAILABLE = ["do you have", "is there", "available", "hai kya", "है क्या", "ಇದೆಯಾ", "ಇದೆಯೇ"]
REPEAT = ["repeat", "say that again", "say again", "once more", "pardon", "come again",
          "दोहराओ", "फिर से", "ಮತ್ತೆ ಹೇಳಿ", "ಇನ್ನೊಮ್ಮೆ"]
# Words that mean "place my order now" (never "yes, add that drink").
PLACE_ORDER = ["confirm", "place the order", "place my order", "proceed", "check out", "checkout",
               "कन्फर्म", "ಕನ್ಫರ್ಮ್"]
REORDER = ["same as last time", "same as before", "same as my last", "my usual", "the usual", "usual order",
           "last order", "previous order", "order again", "reorder", "re-order", "same order",
           "same again", "repeat my order", "repeat my last", "repeat the last",
           "pichli baar", "pichla order", "pichle jaisa", "wahi order", "vahi order",
           "पिछली बार", "पिछला ऑर्डर", "पिछले जैसा", "वही ऑर्डर", "फिर से वही",
           "ಹಿಂದಿನ ಆರ್ಡರ್", "ಹಿಂದಿನ ಬಾರಿ", "ಕಳೆದ ಬಾರಿ", "ಅದೇ ಆರ್ಡರ್"]
GREET = ["hello", "hi", "hey", "namaste", "namaskara", "namaskar", "good morning",
         "good evening", "good afternoon", "नमस्ते", "ನಮಸ್ಕಾರ"]

# Small English notes like "no onion", "extra chutney", "less spicy".
NOTE_PATTERNS = [
    r"(?:no|without)\s+(?:the\s+)?(?:onions?|garlic|chill?ies|chill?i|sugar|chutney|sambar|coriander|ghee|butter|salt)",
    r"extra\s+\w+",
    r"(?:less|little|low)\s+(?:spicy|spice|sugar|sweet|oil|salt)",
    r"(?:more|very)\s+(?:spicy|sweet|crispy)",
]


def parse_rules(text, menu, lang="en"):
    t = mm.clean(text)
    result = {"intent": "unknown", "items": [], "ambiguous": [],
              "notes": [], "bare_quantity": None, "filter": None}
    if not t:
        return result

    # 1. Which dishes were mentioned, and how many of each?
    found = mm.find_items(t, menu)
    vague = mm.find_ambiguous(t, found, menu)
    mentions = sorted(
        [dict(f, kind="item") for f in found] + [dict(v, kind="vague") for v in vague],
        key=lambda m: m["start"],
    )
    for m, (qty, explicit) in zip(mentions, mm.quantities(t, mentions, lang)):
        if m["kind"] == "item":
            result["items"].append({"item_id": m["item"]["id"], "quantity": qty, "explicit": explicit})
        else:
            result["ambiguous"].append({"candidates": [c["id"] for c in m["candidates"]],
                                        "quantity": qty, "explicit": explicit})
    has_items = bool(result["items"] or result["ambiguous"])

    # 2. Small notes such as "no onion".
    # Each note belongs to the dish mentioned just before it ("dosa with no onion").
    dish_mentions = [m for m in mentions if m["kind"] == "item"]
    for pattern in NOTE_PATTERNS:
        for m in re.finditer(pattern, t):
            before = [d for d in dish_mentions if d["end"] <= m.start()]
            after = [d for d in dish_mentions if d["start"] >= m.end()]
            owner = (before[-1] if before else after[0] if after else None)
            result["notes"].append({"text": m.group(0), "item_id": owner["item"]["id"] if owner else None})

    flt = detect_filter(t)

    # 3. What does the customer want to DO?
    nums = mm.number_tokens(t, lang)
    if not has_items and mm.contains(t, CANCEL_ORDER + ["cancel"]):
        result["intent"] = "cancel"
    elif not has_items and mm.contains(t, REORDER):
        result["intent"] = "reorder"
    elif mm.contains(t, REPEAT):
        result["intent"] = "repeat"
    elif not has_items and not flt and mm.contains(t, MENU):
        result["intent"] = "menu"
    elif has_items:
        if mm.contains(t, REMOVE):
            result["intent"] = "remove"
        elif mm.contains(t, MODIFY):
            result["intent"] = "modify"
        elif mm.contains(t, PRICE):
            result["intent"] = "price"
        elif mm.contains(t, AVAILABLE):
            result["intent"] = "availability"
        else:
            result["intent"] = "order"
    elif result["notes"]:
        result["intent"] = "note"
    elif flt:
        result["intent"] = "filter"
        result["filter"] = flt
    elif mm.contains(t, PRICE + TOTAL):
        result["intent"] = "total"
    elif mm.contains(t, DONE):
        result["intent"] = "done"
    elif mm.contains(t, CONFIRM):
        result["intent"] = "confirm"
    elif mm.contains(t, DENY):
        result["intent"] = "deny"
    elif nums and mm.contains(t, MODIFY):
        result["intent"] = "modify"
        result["bare_quantity"] = nums[-1][2]
    elif mm.contains(t, GREET):
        result["intent"] = "greet"
    return result


# ---------- "something vegetarian under 50", "any sweets?" ----------
CATEGORY_WORDS = {
    "Drinks": ["drink", "drinks", "beverage", "beverages", "पेय", "ಪಾನೀಯ"],
    "Sweets": ["sweet", "sweets", "dessert", "desserts", "मीठा", "ಸಿಹಿ"],
    "Tiffin": ["tiffin", "breakfast", "snack", "snacks", "टिफिन", "ಟಿಫಿನ್"],
    "Meals": ["meal", "meals", "lunch", "थाली", "ಊಟ"],
}
VEG_WORDS = ["veg", "vegetarian", "शाकाहारी", "ಸಸ್ಯಾಹಾರಿ"]
NON_VEG_WORDS = ["non veg", "non-veg", "nonveg", "non vegetarian", "मांसाहारी", "ಮಾಂಸಾಹಾರಿ"]
CHEAP_WORDS = ["cheap", "cheapest", "budget", "affordable", "सस्ता", "ಅಗ್ಗ"]
PRICE_LIMIT = re.compile(r"(?:under|below|less than|within|upto|up to|maximum|max)\s*(?:₹|rs|rupees)?\s*(\d{1,4})")


def detect_filter(t):
    flt = {"category": None, "max_price": None, "veg": None, "cheap": False}
    for category, words in CATEGORY_WORDS.items():
        if mm.contains(t, words):
            flt["category"] = category
    if mm.contains(t, NON_VEG_WORDS):
        flt["veg"] = False
    elif mm.contains(t, VEG_WORDS):
        flt["veg"] = True
    m = PRICE_LIMIT.search(t)
    if m:
        flt["max_price"] = int(m.group(1))
    flt["cheap"] = mm.contains(t, CHEAP_WORDS)
    if flt["category"] or flt["veg"] is not None or flt["max_price"] or flt["cheap"]:
        return flt
    return None


# ---------- dine-in / takeaway / table number ----------
TAKEAWAY_WORDS = ["takeaway", "take away", "take-away", "takeout", "parcel", "to go", "carry out", "pack it",
                  "पार्सल", "टेकअवे", "टेक अवे", "ले जाना", "ले जाऊंगा", "ले जाऊँगा",
                  "ಪಾರ್ಸೆಲ್", "ಪಾರ್ಸಲ್", "ಟೇಕ್ ಅವೇ", "ಟೇಕ್ಅವೇ"]
DINE_WORDS = ["dine in", "dine-in", "dining", "eat here", "eating here", "sit here", "for here", "here", "inside",
              "यहीं", "यहाँ", "यहां", "अंदर", "डाइन इन",
              "ಇಲ್ಲೇ", "ಇಲ್ಲಿ", "ಒಳಗೆ", "ಡೈನ್ ಇನ"]
TABLE_WORDS = ["table", "tbl", "टेबल", "टेबिल", "ಟೇಬಲ್"]
TABLE_FILLER = {"number", "no", "num", "is", "#", "नंबर", "संख्या", "ಸಂಖ್ಯೆ", "नं"}


def detect_serving(t, lang, awaiting=None, allow_bare=False):
    """Finds "takeaway", "dine in" or "table 5" in a cleaned sentence.
    Always: a takeaway word, or the word "table" + a number.
    Only when the agent just asked (awaiting "where" or "table"): plain "here"/"inside".
    Only when awaiting "table" and allow_bare: a lone number ("five") is the table number.
    Returns {"type": "takeaway"|"dine-in"|None, "table": "5"|None} or None."""
    found = {"type": None, "table": None}
    if mm.contains(t, TAKEAWAY_WORDS):
        found["type"] = "takeaway"
        return found
    toks = mm.tokens(t)
    for i, (s, e, tok) in enumerate(toks):
        if tok in TABLE_WORDS or any(tok.startswith(w) for w in TABLE_WORDS if not mm.is_latin(w)):
            for _, _, nxt in toks[i + 1:i + 3]:
                if nxt in TABLE_FILLER:
                    continue
                n = int(nxt) if nxt.isdigit() and len(nxt) <= 2 else mm.NUMBER_WORDS.get(nxt)
                if n and 1 <= n <= 99:
                    found["type"], found["table"] = "dine-in", str(n)
                break
    if not found["table"] and awaiting in ("where", "table"):
        if mm.contains(t, DINE_WORDS):
            found["type"] = "dine-in"
        if awaiting == "table" and allow_bare:
            nums = [n for n in mm.number_tokens(t, lang) if 1 <= n[2] <= 99]
            if nums:
                found["type"], found["table"] = "dine-in", str(nums[-1][2])
    return found if (found["type"] or found["table"]) else None


# ---------- customer name / phone / payment mode ----------
NAME_PREFIXES = [
    r"^(?:my name is|i am|i'm|this is|call me)\s+",
    r"^(?:mera naam|naam|hamara naam|मेरा नाम|हमारा नाम|नाम)\s+",
    r"^(?:nanna hesaru|hesaru|ನನ್ನ ಹೆಸರು|ಹೆಸರು)\s+",
]

NAME_MAP = {
    "विकास": "Vikas",
    "राहुल": "Rahul",
    "प्रिया": "Priya",
    "स्नेहा": "Sneha",
    "अमित": "Amit",
}

CASH_WORDS = ["cash", "nakad", "rokhad", "nagadu", "नकद", "ನಗದು", "pay cash", "by cash", "cash payment", "cash on delivery"]
UPI_WORDS = ["upi", "qr", "qr code", "scanner", "scan", "online", "gpay", "google pay",
             "phonepe", "paytm", "bhim", "cashless", "क्यूआर", "यूपीआई", "ಯುಪಿಐ", "ಸ್ಕ್ಯಾನ್", "ಕ್ಯೂಆರ್"]


def extract_name(text):
    """Extract a customer's name from what they said."""
    t = text.strip()
    for prefix in NAME_PREFIXES:
        t = re.sub(prefix, "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+(?:hai|ide|please|sir|madam|है|ಇದೆ)$", "", t, flags=re.IGNORECASE).strip()
    if t in NAME_MAP:
        return NAME_MAP[t]
    words = t.split()
    if 1 <= len(words) <= 3 and all(len(w) <= 20 for w in words):
        return " ".join(NAME_MAP.get(w, w.capitalize()) for w in words)
    return NAME_MAP.get(t, t[:40] if t else None)


def detect_phone(text, lang="en"):
    """Extract a 10-digit Indian phone number from digits or spoken number words."""
    digits = re.findall(r"\d", text)
    if len(digits) == 10:
        return "".join(digits)
    num_tokens = mm.number_tokens(text, lang)
    single_digits = []
    for _, _, val in num_tokens:
        if 0 <= val <= 9:
            single_digits.append(str(val))
        elif 10 <= val <= 99:
            single_digits.extend(list(str(val)))
    if len(single_digits) == 10:
        return "".join(single_digits)
    joined = "".join(digits)
    m = re.search(r"[6-9]\d{9}", joined)
    if m:
        return m.group(0)
    return None


def detect_payment(text):
    """Returns 'cash' or 'upi' or None."""
    t = mm.clean(text)
    if mm.contains(t, CASH_WORDS):
        return "cash"
    if mm.contains(t, UPI_WORDS):
        return "upi"
    return None


# ---------- the function the rest of the app calls ----------
def parse(text, menu, lang="en", context=None):
    """Rules first (fast, free). The LLM helps only when configured and needed.
    result["source"] says who understood the sentence: "rules" or "llm"."""
    rules = parse_rules(text, menu, lang)
    rules["source"] = "rules"
    if llm.wanted(rules, text):
        smart = llm.parse_with_llm(text, menu, lang, context or {})
        # In "always" mode, if the LLM gave up but the rules understood, keep the rules.
        if smart and not (smart["intent"] == "unknown" and rules["intent"] != "unknown"):
            smart["source"] = "llm"
            return smart
    return rules
