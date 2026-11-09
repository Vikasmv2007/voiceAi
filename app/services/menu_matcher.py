"""Finds menu items (and quantities) inside what the customer said."""
import difflib
import re
import unicodedata

# Number words in English, Hindi, Kannada, Tamil and Telugu (Latin and native script).
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "ek": 1, "teen": 3, "char": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "ondu": 1, "eradu": 2, "mooru": 3, "nalku": 4, "naalku": 4,
    "aidu": 5, "aaru": 6, "yelu": 7, "entu": 8, "ombattu": 9, "hattu": 10,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
    "ಆರು": 6, "ಏಳು": 7, "ಎಂಟು": 8, "ಒಂಬತ್ತು": 9, "ಹತ್ತು": 10,
    # Tamil
    "onnu": 1, "rendu": 2, "moonu": 3, "naalu": 4, "anju": 5, "ezhu": 7, "ettu": 8, "onbadhu": 9, "pathu": 10,
    "ஒன்று": 1, "ஒரு": 1, "இரண்டு": 2, "ரெண்டு": 2, "மூன்று": 3, "மூணு": 3, "நான்கு": 4, "நாலு": 4,
    "ஐந்து": 5, "அஞ்சு": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
    # Telugu
    "okati": 1, "moodu": 3, "naalugu": 4, "edu": 7, "enimidi": 8, "tommidi": 9, "padi": 10,
    "ఒకటి": 1, "ఒక": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5,
    "ఆరు": 6, "ఏడు": 7, "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10,
}

NAME_FIELDS = ("name_en", "name_kn", "name_hi", "name_ta", "name_te")

# Different spellings of the same word (used to spot "dosa" in "dose", "dosai").
SYNONYMS = {"dose": "dosa", "dosai": "dosa", "idly": "idli", "iddli": "idli"}


def clean(text):
    """Lower-case, remove punctuation and the Hindi 'nukta' dot so that
    फ़िल्टर and फिल्टर both match."""
    text = unicodedata.normalize("NFC", text or "").lower()
    text = text.replace("़", "")
    text = re.sub(r"[,.;:!?।|\"()]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_latin(s):
    return re.fullmatch(r"[a-z0-9' \-]+", s) is not None


def find_all(text, phrase, plural=False):
    """All (start, end) places where `phrase` appears in `text`.

    English phrases must match whole words. Hindi/Kannada phrases of 3 or
    fewer characters must match a whole word too (otherwise 'ना' would
    match inside 'नाश्ता'); longer ones can match as a prefix of a word."""
    spans = []
    if is_latin(phrase):
        suffix = r"(?:s|es)?" if plural else ""
        pattern = r"(?<![a-z0-9])" + re.escape(phrase) + suffix + r"(?![a-z0-9])"
        spans = [(m.start(), m.end()) for m in re.finditer(pattern, text)]
    elif len(phrase) <= 3:
        spans = [(m.start(), m.end()) for m in re.finditer(r"(?<!\S)" + re.escape(phrase) + r"(?!\S)", text)]
    else:
        start = 0
        while True:
            i = text.find(phrase, start)
            if i < 0:
                break
            spans.append((i, i + len(phrase)))
            start = i + len(phrase)
    return spans


def contains(text, phrases):
    return any(find_all(text, clean(p)) for p in phrases)


def tokens(text):
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text)]


def variants(item):
    names = [item.get(f) for f in NAME_FIELDS]
    names += (item["aliases"] or "").split(",")
    out = [clean(n) for n in names if n and clean(n)]
    return list(dict.fromkeys(out))


def _overlaps(s, e, claimed):
    return any(s < c["end"] and e > c["start"] for c in claimed)


def find_items(text, menu):
    """Return [{'start','end','item'}] for each menu item mentioned."""
    candidates = []
    for item in menu:
        for v in variants(item):
            for s, e in find_all(text, v, plural=True):
                candidates.append((s, e, item))
    # Longest names first, so "masala dosa" wins over plain "masala".
    candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
    claimed = []
    for s, e, item in candidates:
        if not _overlaps(s, e, claimed):
            claimed.append({"start": s, "end": e, "item": item})

    # Fuzzy pass: catches small speech-to-text slips ("masaladosa", "filtr coffee").
    latin_variants = [(v, item) for item in menu for v in variants(item) if is_latin(v)]
    toks = tokens(text)
    for size in (3, 2, 1):
        for i in range(len(toks) - size + 1):
            window = toks[i:i + size]
            s, e = window[0][0], window[-1][1]
            phrase = " ".join(t[2] for t in window)
            if len(phrase) < 5 or not is_latin(phrase) or _overlaps(s, e, claimed):
                continue
            best, best_item = 0.0, None
            for v, item in latin_variants:
                r = difflib.SequenceMatcher(None, phrase, v).ratio()
                if r > best:
                    best, best_item = r, item
            if best >= 0.85:
                claimed.append({"start": s, "end": e, "item": best_item})
    claimed.sort(key=lambda c: c["start"])
    return claimed


def generic_words(menu):
    """Words shared by 2+ dishes, e.g. 'dosa' -> Masala/Plain/Set Dosa.
    If a customer says only 'dosa', we must ask which one."""
    found = {}
    for item in menu:
        for field in NAME_FIELDS:
            for w in set(clean(item.get(field) or "").split()):
                if len(w) >= 3:
                    found.setdefault(w, {})[item["id"]] = item
    return {w: list(items.values()) for w, items in found.items() if len(items) >= 2}


def find_ambiguous(text, claimed, menu):
    """Return [{'start','end','candidates'}] for vague words like 'dosa'."""
    generic = generic_words(menu)
    result = []
    for s, e, tok in tokens(text):
        if _overlaps(s, e, claimed):
            continue
        word = SYNONYMS.get(tok, tok)
        if word.endswith("s") and word[:-1] in generic:
            word = word[:-1]
        match = generic.get(word)
        if match is None and not is_latin(word):
            for g, items in generic.items():
                if len(g) >= 4 and word.startswith(g):
                    match = items
                    break
        if match:
            result.append({"start": s, "end": e, "candidates": match})
    return result


def parse_addons(item):
    """'Extra Cheese:15, Extra Chutney:10' -> [("Extra Cheese", 15), ("Extra Chutney", 10)]."""
    out = []
    for part in (item.get("addons") or "").split(","):
        name, colon, price = part.partition(":")
        name = name.strip()
        try:
            price = int(price.strip())
        except ValueError:
            continue
        if not colon:
            continue
        if name and 0 <= price <= 5000:
            out.append((name, price))
    return out


def number_tokens(text, lang):
    found = []
    for s, e, tok in tokens(text):
        if tok.isdigit() and len(tok) <= 2:
            found.append((s, e, int(tok)))
        elif tok in NUMBER_WORDS:
            found.append((s, e, NUMBER_WORDS[tok]))
        elif tok == "do" and lang == "hi":      # Hindi "do" = two (English "do" is common!)
            found.append((s, e, 2))
    return found


def quantities(text, mentions, lang):
    """For each mention work out (quantity, was_it_said_explicitly)."""
    nums = number_tokens(text, lang)
    out = []
    for i, m in enumerate(mentions):
        prev_end = mentions[i - 1]["end"] if i > 0 else 0
        next_start = mentions[i + 1]["start"] if i + 1 < len(mentions) else len(text)
        left = [n for n in nums if n[0] >= prev_end and n[1] <= m["start"]]
        if left:
            out.append((left[-1][2], True))
            continue
        right = [n for n in nums if n[0] >= m["end"] and n[1] <= next_start]
        if right:
            between = text[m["end"]:right[0][0]].strip()
            is_last = i == len(mentions) - 1
            if between in ("to", "x", "×") or (is_last and between == ""):
                out.append((right[0][2], True))
                continue
        out.append((1, False))
    return out
