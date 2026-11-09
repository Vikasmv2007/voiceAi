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
           "ಹೌದು", "ಸರಿ", "ಹೂಂ", "ಕನ್ಫರ್ಮ್", "houdu", "sari",
           "ஆமா", "ஆம்", "சரி", "சரிங்க", "உறுதி", "aama", "seri",
           "అవును", "సరే", "కన్ఫర్మ్", "avunu", "sare"]
DENY = ["no", "nope", "nahi", "nahin", "नहीं", "नही", "ना", "ಇಲ್ಲ", "ಬೇಡ",
        "இல்லை", "வேண்டாம்", "illa", "vendam", "లేదు", "వద్దు", "ledu", "vaddu"]
DONE = ["that's all", "thats all", "that is all", "that is it", "that's it", "thats it",
        "nothing else", "nothing more", "no more", "that will be all", "bas", "बस",
        "ಅಷ್ಟೇ", "ಸಾಕು", "அவ்வளவு தான்", "அவ்வளவுதான்", "போதும்", "podhum", "అంతే", "చాలు", "ante", "chaalu"]
REMOVE = ["remove", "delete", "take off", "take out", "don't want", "dont want", "cancel",
          "hata", "hatao", "nikal", "nikalo", "हटा", "हटाओ", "निकाल", "निकालो",
          "ಬೇಡ", "ತೆಗೆ", "ತೆಗೆದು", "beda", "நீக்கு", "வேண்டாம்", "తీసేయి", "తీసెయ్యి", "వద్దు"]
MODIFY = ["change", "make it", "make that", "instead", "update", "set it", "only",
          "badal", "बदल", "ಬದಲಾಯಿಸಿ", "ಬದಲು"]
CANCEL_ORDER = ["cancel order", "cancel my order", "cancel the order", "cancel everything",
                "cancel all", "start over", "clear order", "कैंसिल", "ऑर्डर रद्द", "ರದ್ದು", "ரத்து", "రద్దు"]
PRICE = ["price", "cost", "rate", "how much", "कीमत", "दाम", "ಬೆಲೆ", "ದರ", "விலை", "எவ்வளவு", "ధర", "ఎంత"]
TOTAL = ["total", "bill", "amount", "kitna", "kitne", "कितना", "कितने", "कुल", "बिल",
         "ಎಷ್ಟು", "ಒಟ್ಟು", "ಬಿಲ್", "மொத்தம்", "பில்", "మొత్తం", "బిల్"]
MENU = ["menu", "what do you have", "what all", "what is available", "what's available",
        "whats available", "what can i order", "options", "recommend", "suggest",
        "popular", "special", "मेनू", "मेन्यू", "क्या है", "क्या मिलेगा", "ಮೆನು", "ಏನಿದೆ",
        "மெனு", "என்ன இருக்கு", "మెనూ", "ఏమున్నాయి", "ఏం ఉంది"]
AVAILABLE = ["do you have", "is there", "available", "hai kya", "है क्या", "ಇದೆಯಾ", "ಇದೆಯೇ",
             "இருக்கா", "கிடைக்குமா", "ఉందా", "దొరుకుతుందా"]
REPEAT = ["repeat", "say that again", "say again", "once more", "pardon", "come again",
          "दोहराओ", "फिर से", "ಮತ್ತೆ ಹೇಳಿ", "ಇನ್ನೊಮ್ಮೆ", "மீண்டும் சொல்லுங்கள்", "திரும்ப சொல்லுங்க", "మళ్ళీ చెప్పండి"]
# Words that mean "place my order now" (never "yes, add that drink").
PLACE_ORDER = ["confirm", "place the order", "place my order", "proceed", "check out", "checkout",
               "कन्फर्म", "ಕನ್ಫರ್ಮ್", "உறுதி", "కన్ఫర్మ్"]
REORDER = ["same as last time", "same as before", "same as my last", "my usual", "the usual", "usual order",
           "last order", "previous order", "order again", "reorder", "re-order", "same order",
           "same again", "repeat my order", "repeat my last", "repeat the last",
           "pichli baar", "pichla order", "pichle jaisa", "wahi order", "vahi order",
           "पिछली बार", "पिछला ऑर्डर", "पिछले जैसा", "वही ऑर्डर", "फिर से वही",
           "ಹಿಂದಿನ ಆರ್ಡರ್", "ಹಿಂದಿನ ಬಾರಿ", "ಕಳೆದ ಬಾರಿ", "ಅದೇ ಆರ್ಡರ್"]
GREET = ["hello", "hi", "hey", "namaste", "namaskara", "namaskar", "good morning",
         "good evening", "good afternoon", "नमस्ते", "ನಮಸ್ಕಾರ", "வணக்கம்", "vanakkam", "నమస్కారం", "namaskaram"]
# "Is masala dosa spicy?", "How sweet is kesari?"
DESCRIBE_QUESTION = r"^(?:is|are|how|does|do)\b.*\b(?:spicy|sweet|hot|veg|vegetarian|vegan|oily|healthy)\b"
# "What is pongal?", "Is it spicy?"
DESCRIBE = ["what is", "what's", "whats", "what are", "tell me about", "describe", "ingredients", "made of",
            "is it spicy", "is it veg", "kya hota", "क्या होता", "क्या है", "बताइए", "ಅಂದರೆ ಏನು", "ಏನು ಇದು",
            "என்றால் என்ன", "என்ன அது", "అంటే ఏమిటి", "ఏమిటి"]

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
              "notes": [], "bare_quantity": None, "filter": None, "addons": []}
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

    dish_mentions = [m for m in mentions if m["kind"] == "item"]

    def owner_of(start, end):
        """A note / add-on belongs to the dish said just before it, else the one just after."""
        before = [d for d in dish_mentions if d["end"] <= start]
        after = [d for d in dish_mentions if d["start"] >= end]
        owner = before[-1] if before else after[0] if after else None
        return owner["item"] if owner else None

    # 2. Paid add-ons from the menu ("masala dosa with extra cheese").
    addon_spans = []
    for item in menu:
        for name, price in mm.parse_addons(item):
            for s_, e_ in mm.find_all(t, mm.clean(name)):
                owner = owner_of(s_, e_)
                result["addons"].append({"item_id": owner["id"] if owner else None, "name": name, "price": price,
                                         "menu_item_id": item["id"]})
                addon_spans.append((s_, e_))
    # Keep only add-ons that belong to the dish they were said with (or to no dish yet).
    result["addons"] = [a for a in result["addons"] if a["item_id"] in (None, a["menu_item_id"])]
    seen = set()
    result["addons"] = [a for a in result["addons"]
                        if (a["name"], a["item_id"]) not in seen and not seen.add((a["name"], a["item_id"]))]

    # 3. Small free notes such as "no onion" (not the paid add-ons above).
    for pattern in NOTE_PATTERNS:
        for m in re.finditer(pattern, t):
            if any(m.start() < e_ and m.end() > s_ for s_, e_ in addon_spans):
                continue
            owner = owner_of(m.start(), m.end())
            result["notes"].append({"text": m.group(0), "item_id": owner["id"] if owner else None})

    flt = detect_filter(t, menu)

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
        elif not result["addons"] and (mm.contains(t, DESCRIBE) or re.match(DESCRIBE_QUESTION, t)):
            result["intent"] = "describe"
        else:
            result["intent"] = "order"
    elif result["addons"]:
        result["intent"] = "addon"
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


def detect_filter(t, menu=()):
    flt = {"category": None, "max_price": None, "veg": None, "cheap": False}
    for category, words in CATEGORY_WORDS.items():
        if mm.contains(t, words):
            flt["category"] = category
    # Categories the owner added in the menu editor ("Chinese", "Juices") work too.
    for category in {m["category"] for m in menu} - set(CATEGORY_WORDS):
        if category and mm.contains(t, [category]):
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
                  "ಪಾರ್ಸೆಲ್", "ಪಾರ್ಸಲ್", "ಟೇಕ್ ಅವೇ", "ಟೇಕ್ಅವೇ", "பார்சல்", "పార్సిల్", "పార్శిల్"]
DINE_WORDS = ["dine in", "dine-in", "dining", "eat here", "eating here", "sit here", "for here", "here", "inside",
              "यहीं", "यहाँ", "यहां", "अंदर", "डाइन इन",
              "ಇಲ್ಲೇ", "ಇಲ್ಲಿ", "ಒಳಗೆ", "ಡೈನ್ ಇನ", "இங்கே", "இங்க", "ఇక్కడే", "ఇక్కడ"]
TABLE_WORDS = ["table", "tbl", "टेबल", "टेबिल", "ಟೇಬಲ್", "டேபிள்", "టేబుల్"]
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
    r"^(?:en peyar|en peru|என் பெயர்|என் பேரு|என் பெயர்)\s+",
    r"^(?:naa peru|నా పేరు)\s+",
]

NAME_MAP = {
    "विकास": "Vikas",
    "राहुल": "Rahul",
    "प्रिया": "Priya",
    "स्नेहा": "Sneha",
    "अमित": "Amit",
}

# "I'm done", "I am ready" ... are not names.
NOT_NAMES = {"done", "ready", "fine", "good", "ok", "okay", "finished", "hungry", "here", "back", "sorry",
             "not sure", "thinking", "waiting", "full"}

CASH_WORDS = ["cash", "nakad", "rokhad", "nagadu", "नकद", "ನಗದು", "pay cash", "by cash", "cash payment", "cash on delivery",
              "ரொக்கம்", "கேஷ்", "నగదు", "క్యాష్"]
UPI_WORDS = ["upi", "qr", "qr code", "scanner", "scan", "online", "gpay", "google pay",
             "phonepe", "paytm", "bhim", "cashless", "क्यूआर", "यूपीआई", "ಯುಪಿಐ", "ಸ್ಕ್ಯಾನ್", "ಕ್ಯೂಆರ್",
             "யுபிஐ", "ஸ்கேன்", "యూపీఐ", "స్కాన్"]


def explicit_name(text):
    """A name only when the customer clearly introduced it ("my name is Ravi", "I am Ravi")."""
    t = text.strip()
    if any(re.match(prefix, t, flags=re.IGNORECASE) for prefix in NAME_PREFIXES):
        name = extract_name(t)
        if name and name.lower() not in NOT_NAMES:
            return name
    return None


def extract_name(text):
    """Extract a customer's name from what they said."""
    t = text.strip()
    for prefix in NAME_PREFIXES:
        t = re.sub(prefix, "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+(?:hai|ide|please|sir|madam|है|ಇದೆ|தான்|ங்க)$", "", t, flags=re.IGNORECASE).strip()
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


# ---------- which language is this written in? ----------
SCRIPTS = [("hi", 0x0900, 0x097F), ("te", 0x0C00, 0x0C7F), ("kn", 0x0C80, 0x0CFF), ("ta", 0x0B80, 0x0BFF)]


def detect_language(text):
    """'hi' / 'kn' / 'ta' / 'te' when most letters are in that script, else None (Latin text:
    we cannot tell Hinglish from English, so the selected language is kept)."""
    counts = {}
    for ch in text or "":
        code = ord(ch)
        for lang, low, high in SCRIPTS:
            if low <= code <= high:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return None
    lang, n = max(counts.items(), key=lambda kv: kv[1])
    return lang if n >= 2 else None


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
            smart.setdefault("addons", rules["addons"])       # add-on prices always come from the menu
            return smart
    return rules
