from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import re


AGGREGATION_KEYWORDS = {
    # Count
    "count": "count",
    "number": "count",
    "many": "count",
    # Average
    "average": "avg",
    "avg": "avg",
    "mean": "avg",
    # Sum
    "sum": "sum",
    "total": "sum",
    # Max
    "max": "max",
    "maximum": "max",
    "highest": "max",
    # Min
    "min": "min",
    "minimum": "min",
    "lowest": "min",
}

COMPARISON_GT = {"older", "greater", "more", "above", "over", "higher", "bigger"}
COMPARISON_LT = {"younger", "less", "fewer", "below", "under", "lower", "smaller"}
SHOW_KEYWORDS = {"show", "list", "find", "get", "display", "fetch", "all", "select",
                 "what", "which", "give", "tell", "return", "retrieve", "pull",
                 "please", "can", "could", "want", "need", "see",
                 "who", "when", "where", "how"}
PROJECTION_KEYWORDS = {"show", "display", "select", "return", "get", "only",
                       "what", "which", "give", "tell", "retrieve",
                       "find", "list"}

# Words that introduce a condition clause — equivalent to "where"
_CONDITION_TRIGGERS = {
    "where", "with", "having", "whose", "when", "if",
    "that", "which",
}

# Words that are structural in question/projection context and should be
# skipped over when scanning for projected field names.
_PROJECTION_FILLER = {
    "me", "the", "a", "an", "my", "all", "its",
    "entire", "complete", "full", "whole",
    "row", "rows", "record", "records", "document", "documents",
    "doc", "docs", "entry", "entries",
    "data", "value", "values", "field", "fields", "column", "columns",
    "is", "are", "was", "were", "from",  # question structure
    "please", "can", "could", "would", "will",
    "you", "i", "want", "need", "to", "see",
    "have", "has", "do", "does",
    "tell", "about",
    "currently", "specific", "particular", "exact", "certain",
    "every", "any", "some", "each", "our", "their", "your",
    "information", "info", "details", "detail",
    "everything", "anything", "something",
    "contact", "current", "new", "old", "open", "closed",
}

# Noise words that should never match against field names
_NOISE = {
    "show", "list", "find", "get", "display", "fetch", "all", "select",
    "records", "documents", "docs", "entries", "rows", "results",
    "where", "and", "or", "the", "a", "an", "of", "for", "with",
    "is", "are", "was", "were", "not", "no", "to", "from", "by",
    "in", "on", "at", "that", "this", "it", "its", "my", "me",
    "which", "who", "what", "how", "many", "much", "than",
    "greater", "less", "more", "fewer", "above", "below", "over", "under",
    "older", "younger", "higher", "lower", "bigger", "smaller",
    "sorted", "sort", "order", "ordered", "limit", "top", "first",
    "ascending", "descending", "asc", "desc", "up", "down",
    "count", "average", "avg", "sum", "total", "max", "min",
    "maximum", "minimum", "highest", "lowest", "mean", "number",
    "equals", "equal",
    "contains", "containing", "includes", "including", "has",
    "like", "matches", "matching",
    "please", "can", "could", "would", "you", "want", "need",
    "i", "do", "does", "tell", "about", "give", "between",
    "having", "whose", "when", "if",
    "without", "excluding", "except", "but",
    "row", "column", "field", "value",
    "today", "yesterday", "tomorrow", "currently", "recently", "ago",
    "our", "their", "your", "his", "her",
    "best", "worst", "newest", "oldest", "cheapest",
    "fastest", "slowest", "latest", "earliest",
    "every", "any", "some", "each",
    "made", "did", "got", "went", "came",
    "money", "figures", "details", "information", "info",
    "everything", "anything", "something",
}

# Clause-break words that stop condition scanning
_CLAUSE_BREAKS = {
    "sorted", "sort", "ordered", "limit", "top", "first",
    "ascending", "descending", "asc", "desc",
}

# Operator keywords grouped by operator type
_OP_EQ = {"is", "=", "equals", "equal", "==", "being"}
_OP_NEQ = {"not", "isnt", "isn't", "!=", "ne", "except", "excluding"}
_OP_CONTAINS = {
    "contains", "containing", "includes", "including",
    "like", "matches", "matching",
}
_OP_GT = {"greater", "more", "above", "over", "higher", ">", "after", "bigger"}
_OP_GTE = {">=", "gte", "atleast", "minimum"}
_OP_LT = {"less", "fewer", "below", "under", "lower", "<", "before", "smaller"}
_OP_LTE = {"<=", "lte", "atmost", "maximum"}

# --- Temporal expressions ---
_TEMPORAL_SINGLE = {"today", "yesterday", "tomorrow", "now"}
_TEMPORAL_MODIFIERS = {"last", "this", "next", "past", "previous", "current"}
_TEMPORAL_UNITS = {
    "day", "days", "week", "weeks", "month", "months",
    "quarter", "quarters", "year", "years",
    "hour", "hours", "minute", "minutes",
}
_TEMPORAL_ALL = _TEMPORAL_SINGLE | _TEMPORAL_MODIFIERS | _TEMPORAL_UNITS

# --- Currency / number helpers ---
_CURRENCY_RE = re.compile(r'^[\$\u20ac\u00a3\u00a5\u20b9#]+')

# --- Superlative keywords \u2192 sort direction ---
_SUPERLATIVE_DESC = {
    "best", "top", "highest", "most", "biggest", "largest",
    "greatest", "fastest", "newest", "latest", "busiest",
    "maximum", "richest",
}
_SUPERLATIVE_ASC = {
    "worst", "bottom", "lowest", "least", "smallest",
    "fewest", "slowest", "oldest", "earliest", "cheapest",
    "poorest", "minimum",
}

# --- Question word \u2192 field-name hints for auto-projection ---
_QUESTION_FIELD_HINTS = {
    "who": ["name", "employee", "person", "user", "customer",
            "salesperson", "rep", "agent", "staff", "manager", "contact"],
    "when": ["date", "time", "created", "updated", "hired", "joined",
             "timestamp", "created_at", "updated_at"],
    "where": ["city", "location", "address", "region", "state",
              "country", "office", "branch", "store", "warehouse"],
}

# --- Category / context nouns for \"in the X \u2026\" patterns ---
_IN_CONTEXT_NOUNS = {
    "department", "category", "office", "branch", "region",
    "division", "team", "group", "section", "unit",
    "store", "warehouse", "location", "city", "state",
    "country", "area", "zone", "district", "class",
}

# --- Contraction \u2192 expanded negation ---
_CONTRACTIONS_NEG = {
    "haven't": "have not", "hasn't": "has not",
    "hadn't": "had not", "didn't": "did not",
    "doesn't": "does not", "don't": "do not",
    "won't": "will not", "wouldn't": "would not",
    "couldn't": "could not", "shouldn't": "should not",
    "isn't": "is not", "aren't": "are not",
    "wasn't": "was not", "weren't": "were not",
    "can't": "can not",
}


# ---------------------- PREPROCESSING ----------------------

# Polite / conversational prefixes to strip
_POLITE_PREFIXES = [
    r"^(?:please\s+)?(?:can|could|would|will)\s+you\s+(?:please\s+)?",
    r"^(?:please\s+)",
    r"^(?:let\s+me\s+(?:see|know|have)\s+)",
    r"^(?:i\s+(?:am|was)\s+(?:looking\s+for|interested\s+in)\s+)",
    r"^(?:do|does)\s+(?:the\s+)?(?:collection|database|table|data)\s+(?:have|contain)\s+",
]


def _preprocess_query(raw: str) -> str:
    """Strip polite/conversational prefixes, expand contractions, and
    remove filler phrases so the core query is exposed.

    Examples:
        'can you please show me records where order is 1'
            \u2192 'show me records where order is 1'
        'please list all'
            \u2192 'list all'
        \"haven't bought anything\" \u2192 \"have not bought anything\"
    """
    text = raw.strip()
    # Expand contractions (haven't \u2192 have not, etc.)
    lowered = text.lower()
    for contraction, expansion in _CONTRACTIONS_NEG.items():
        if contraction in lowered:
            idx = lowered.index(contraction)
            text = text[:idx] + expansion + text[idx + len(contraction):]
            lowered = text.lower()
    # Strip possessive pronouns (our, my, their, etc.)
    text = re.sub(
        r"\b(our|my|their|your|his|her|its|the\s+company'?s?)\b",
        "", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip()
    lowered = text.lower()
    for pat in _POLITE_PREFIXES:
        m = re.match(pat, lowered)
        if m:
            text = text[m.end():].strip()
            lowered = text.lower()
    # Strip common filler phrases
    _filler_phrases = [
        r"\ba\s+list\s+of\b",
        r"\bthe\s+details?\s+of\b",
        r"\bthe\s+specific\b",
        r"\bthe\s+exact\b",
        r"\bright\s+now\b",
        r"\bat\s+the\s+moment\b",
        r"\bat\s+this\s+point\b",
    ]
    for fp in _filler_phrases:
        text = re.sub(fp, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    # Strip trailing sentence punctuation
    text = text.rstrip("?!.;:")
    return text


def _normalize_number(raw: str):
    """Strip currency symbols ($, \u20ac, etc.), commas, # prefix, and handle
    k/M/B suffixes.  Returns int | float | original string.

    Examples:  '$500' \u2192 500,  '10,000' \u2192 10000,  '#12345' \u2192 12345,
               '10k' \u2192 10000,  '1.5M' \u2192 1500000
    """
    s = raw.strip()
    s = _CURRENCY_RE.sub("", s)
    s = s.replace(",", "")
    if not s:
        return raw
    _suffixes = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if s and s[-1].lower() in _suffixes:
        mult = _suffixes[s[-1].lower()]
        s = s[:-1]
        try:
            return int(float(s) * mult)
        except ValueError:
            return raw
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return raw


def _build_temporal_range(words: List[str], start: int):
    """Detect a temporal expression starting at *start*.

    Returns ``(date_range_dict, words_consumed)`` or ``(None, 0)``.
    *date_range_dict* has keys ``gte`` and/or ``lte`` with ISO date strings.
    """
    if start >= len(words):
        return None, 0
    now = datetime.now()
    w = words[start]

    # --- Single-word temporals ---
    if w == "today":
        d = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return {"gte": d.isoformat(), "lte": (d + timedelta(days=1)).isoformat()}, 1
    if w == "yesterday":
        d = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return {"gte": d.isoformat(), "lte": (d + timedelta(days=1)).isoformat()}, 1
    if w == "tomorrow":
        d = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return {"gte": d.isoformat(), "lte": (d + timedelta(days=1)).isoformat()}, 1

    # --- "last/this/next N <unit>" e.g. "last 6 months", "last 24 hours" ---
    if w in _TEMPORAL_MODIFIERS and start + 2 < len(words):
        try:
            n = int(words[start + 1])
            unit = words[start + 2].rstrip("s")  # normalize plural
            delta = None
            if unit == "day":
                delta = timedelta(days=n)
            elif unit == "week":
                delta = timedelta(weeks=n)
            elif unit == "month":
                delta = timedelta(days=n * 30)
            elif unit == "year":
                delta = timedelta(days=n * 365)
            elif unit == "hour":
                delta = timedelta(hours=n)
            elif unit == "minute":
                delta = timedelta(minutes=n)
            if delta:
                if w in ("last", "past", "previous"):
                    s_dt, e_dt = now - delta, now
                elif w == "next":
                    s_dt, e_dt = now, now + delta
                else:
                    s_dt, e_dt = now - delta, now
                return {"gte": s_dt.isoformat(), "lte": e_dt.isoformat()}, 3
        except ValueError:
            pass

    # --- "last/this/next <unit>" (no number) ---
    if w in _TEMPORAL_MODIFIERS and start + 1 < len(words):
        unit = words[start + 1].rstrip("s")
        if unit == "week":
            if w in ("last", "past", "previous"):
                s = (now - timedelta(weeks=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                return {"gte": s.isoformat(), "lte": now.isoformat()}, 2
            elif w in ("this", "current"):
                s = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                return {"gte": s.isoformat(), "lte": now.isoformat()}, 2
            elif w == "next":
                return {"gte": now.isoformat(), "lte": (now + timedelta(weeks=1)).isoformat()}, 2
        if unit == "month":
            if w in ("last", "past", "previous"):
                first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_end = first_this - timedelta(days=1)
                s = last_end.replace(day=1)
                return {"gte": s.isoformat(), "lte": first_this.isoformat()}, 2
            elif w in ("this", "current"):
                s = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                return {"gte": s.isoformat(), "lte": now.isoformat()}, 2
            elif w == "next":
                nm = now.month % 12 + 1
                ny = now.year + (1 if now.month == 12 else 0)
                s = datetime(ny, nm, 1)
                nm2 = nm % 12 + 1
                ny2 = ny + (1 if nm == 12 else 0)
                e = datetime(ny2, nm2, 1)
                return {"gte": s.isoformat(), "lte": e.isoformat()}, 2
        if unit == "quarter":
            if w in ("last", "past", "previous"):
                s = now - timedelta(days=90)
                return {"gte": s.isoformat(), "lte": now.isoformat()}, 2
            elif w in ("this", "current"):
                cq = (now.month - 1) // 3
                s = datetime(now.year, cq * 3 + 1, 1)
                return {"gte": s.isoformat(), "lte": now.isoformat()}, 2
        if unit == "year":
            if w in ("last", "past", "previous"):
                return {"gte": datetime(now.year - 1, 1, 1).isoformat(),
                        "lte": datetime(now.year, 1, 1).isoformat()}, 2
            elif w in ("this", "current"):
                return {"gte": datetime(now.year, 1, 1).isoformat(),
                        "lte": now.isoformat()}, 2
            elif w == "next":
                return {"gte": datetime(now.year + 1, 1, 1).isoformat(),
                        "lte": datetime(now.year + 2, 1, 1).isoformat()}, 2

    return None, 0


# ---------------------- FUZZY / PLURAL FIELD MATCHING ----------------------

def _normalize_singular(word: str) -> str:
    """Naive singular form: strips trailing 's' / 'es'."""
    w = word.lower()
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if w.endswith("ses") or w.endswith("xes") or w.endswith("zes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        return w[:-1]
    return w


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_field_match(word: str, fields: List[str]) -> Optional[str]:
    """Match *word* against schema field names.

    Strategy (in priority order):
    1. Exact case-insensitive match.
    2. Last-segment match for dot-notation fields.
    3. Dot-notation input: user typed ``award.tech`` → match ``awards.tech``.
    4. Singular/plural normalization (``award`` ↔ ``awards``).
    5. Fuzzy similarity ≥ 0.80 as last resort.
    """
    wl = word.lower()

    # 1. exact match
    for field in fields:
        if field.lower() == wl:
            return field

    # 2. last-segment match for nested fields
    for field in fields:
        if "." in field:
            last_segment = field.rsplit(".", 1)[-1]
            if last_segment.lower() == wl:
                return field

    # 3. dot-notation input from user (e.g. "award.tech" → "awards.tech")
    if "." in wl:
        user_segments = wl.split(".")
        for field in fields:
            if "." not in field:
                continue
            field_segments = field.lower().split(".")
            if len(user_segments) != len(field_segments):
                continue
            # check each segment with singular/plural tolerance
            if all(
                _normalize_singular(us) == _normalize_singular(fs)
                for us, fs in zip(user_segments, field_segments)
            ):
                return field

    # 4. singular/plural normalization (only match against LAST segment
    #    to avoid parent-prefix false positives like "options" matching
    #    "options.type" — the user should say "type", not "options")
    w_norm = _normalize_singular(wl)
    for field in fields:
        # For flat fields, compare directly
        if "." not in field:
            if _normalize_singular(field.lower()) == w_norm:
                return field
        else:
            # For dot-notation, only match the leaf (last) segment
            last_seg = field.rsplit(".", 1)[-1].lower()
            if _normalize_singular(last_seg) == w_norm:
                return field

    # 5. fuzzy similarity (threshold 0.80)
    #    For dot-notation fields, only compare against the LAST segment
    #    to prevent parent prefixes like "options" from fuzzy-matching
    #    against "options.id" (full path).
    best_score = 0.0
    best_field = None
    for field in fields:
        if "." in field:
            # Only fuzzy-match against the leaf segment
            leaf = field.rsplit(".", 1)[-1].lower()
            score = _similarity(wl, leaf)
        else:
            score = _similarity(wl, field.lower())
        if score > best_score:
            best_score = score
            best_field = field
    if best_score >= 0.80 and best_field is not None:
        return best_field

    return None


def _find_multi_word_field(words: List[str], start_idx: int, fields: List[str]) -> Optional[str]:
    """Try to match dot-notation fields using consecutive words.

    Example: ``address city`` → ``address.city``

    Also handles singular/plural variations:
    ``award tech`` → ``awards.tech``

    Prefers the longest (most specific) match.
    """
    best_match: Optional[str] = None
    best_length = 0

    for field in fields:
        if "." not in field:
            continue
        segments = field.lower().split(".")
        num_segments = len(segments)
        if start_idx + num_segments > len(words):
            continue
        if num_segments <= best_length:
            continue  # already have a longer/equal match
        candidate = words[start_idx:start_idx + num_segments]

        # Exact segment match
        if candidate == segments:
            best_match = field
            best_length = num_segments
            continue

        # Singular/plural normalized match
        if all(
            _normalize_singular(c) == _normalize_singular(s)
            for c, s in zip(candidate, segments)
        ):
            best_match = field
            best_length = num_segments

    return best_match


def _detect_projection(
    words: List[str],
    allowed_fields: List[str],
) -> Optional[List[str]]:
    """Detect projection intent from the query.

    Patterns recognised:
    - "show name and age"
    - "only name, age"
    - "select name age city"
    - "what is the text where ..." (question-word projection)
    - "show me the text where ..."  (filler words skipped)
    - "give me the row where ..."   ("row" treated as filler)

    Field names take priority over break words — e.g. if the collection
    has a field called ``order``, "show order" correctly projects it
    rather than breaking at the keyword.
    """
    projection: List[str] = []

    for trigger in PROJECTION_KEYWORDS:
        if trigger not in words:
            continue
        idx = words.index(trigger)
        i = idx + 1
        while i < len(words):
            w = words[i]
            # conjunction — skip
            if w in ("and", ",", "&"):
                i += 1
                continue
            # question / filler words — skip
            if w in _PROJECTION_FILLER:
                i += 1
                continue
            # Try matching against a field FIRST so that field names
            # that collide with clause keywords (e.g. "order") still
            # get projected.
            match = _find_field_match(w, allowed_fields)
            if match:
                if match not in projection:
                    projection.append(match)
                i += 1
                continue
            # Try multi-word dot-notation field
            mw = _find_multi_word_field(words, i, allowed_fields)
            if mw:
                if mw not in projection:
                    projection.append(mw)
                i += len(mw.split("."))
                continue
            # Word is neither filler nor a field — stop scanning
            break

    # Only return projection if we found fields that aren't the full set
    if projection and len(projection) < len(allowed_fields):
        return projection

    return None


def parse_to_ir(
    user_input: str,
    allowed_fields: List[str] = None,
    numeric_fields: List[str] = None,
) -> Optional[Dict[str, Any]]:
    """Parse a natural-language query into an intermediate representation.

    Parameters
    ----------
    user_input : str
        Raw query typed by the user.
    allowed_fields : list[str] | None
        All field names from the collection schema (auto-detected).
    numeric_fields : list[str] | None
        Subset of *allowed_fields* whose sample value is numeric.
    """

    if allowed_fields is None:
        allowed_fields = []
    if numeric_fields is None:
        numeric_fields = []

    string_fields = [f for f in allowed_fields if f not in numeric_fields]

    # Preprocess: strip polite / conversational prefixes
    cleaned = _preprocess_query(user_input)

    # -------- EXTRACT ARRAY LITERALS --------
    # Detect JSON-style array literals like ["a","b","c"] BEFORE
    # lower-casing / splitting so we preserve the original values.
    _array_literals: Dict[str, list] = {}  # placeholder → parsed list
    _array_re = re.compile(r'\[\s*["\'][^\]]*["\']\s*\]')
    _arr_idx = 0
    for _arr_m in _array_re.finditer(cleaned):
        raw_arr = _arr_m.group()
        try:
            import json as _json
            parsed = _json.loads(raw_arr)
            if isinstance(parsed, list):
                placeholder = f"__ARRAY_{_arr_idx}__"
                _array_literals[placeholder] = parsed
                cleaned = cleaned[:_arr_m.start()] + placeholder + cleaned[_arr_m.end():]
                _arr_idx += 1
        except Exception:
            pass

    user_lower = cleaned.lower()
    words = user_lower.split()

    conditions: List[Dict[str, Any]] = []
    sort = None
    limit = None
    aggregation = None
    operation = "find"
    projection = None

    # -------- DETECT AGGREGATION --------

    if "how" in words and "many" in words:
        operation = "aggregate"
        aggregation = {"type": "count", "field": None}
    elif "how" in words and "much" in words:
        operation = "aggregate"
        # "how much" \u2192 sum aggregation on best numeric field
        agg_field = None
        _revenue_hints = ("revenue", "sales", "amount", "price", "total",
                          "cost", "money", "income", "salary", "payment",
                          "profit", "spend", "earning", "fee")
        for field in numeric_fields:
            fl = field.lower()
            if any(h in fl for h in _revenue_hints):
                agg_field = field
                break
        if agg_field is None and numeric_fields:
            agg_field = numeric_fields[0]
        aggregation = {"type": "sum", "field": agg_field}
    else:
        for word in words:
            if word in AGGREGATION_KEYWORDS:
                operation = "aggregate"
                agg_type = AGGREGATION_KEYWORDS[word]
                if agg_type == "count":
                    aggregation = {"type": "count", "field": None}
                else:
                    # find which numeric field the user referenced
                    for field in numeric_fields:
                        if field.lower() in words:
                            aggregation = {"type": agg_type, "field": field}
                            break
                        # match on last segment for nested numeric fields
                        if "." in field:
                            last = field.rsplit(".", 1)[-1]
                            if last.lower() in words:
                                aggregation = {"type": agg_type, "field": field}
                                break
                    # fallback: first numeric field
                    if aggregation is None and numeric_fields:
                        aggregation = {"type": agg_type, "field": numeric_fields[0]}
                break

    # -------- DETECT PROJECTION (only for find) --------

    if operation == "find":
        projection = _detect_projection(words, allowed_fields)

    # -------- "in <value>" → string / location field --------

    if "in" in words:
        idx = words.index("in")
        if idx + 1 < len(words):
            location_hints = [
                "city", "location", "state", "country",
                "region", "address", "town",
            ]

            # Skip "the" after "in"
            _in_start = idx + 1
            if words[_in_start] == "the" and _in_start + 1 < len(words):
                _in_start += 1

            # --- Enhanced: "in the X <context-noun>" pattern ---
            # e.g. "in the marketing department", "in the Home Electronics category"
            _in_handled = False
            for _in_scan in range(_in_start, min(_in_start + 6, len(words))):
                _in_w = words[_in_scan]
                _in_ctx_field = _find_field_match(_in_w, string_fields)
                if _in_ctx_field or _in_w in _IN_CONTEXT_NOUNS:
                    if _in_scan > _in_start:  # there are value words before the context noun
                        _in_val = " ".join(words[_in_start:_in_scan])
                        _in_target = _in_ctx_field or _find_field_match(_in_w, allowed_fields)
                        if _in_target and not any(c["field"] == _in_target for c in conditions):
                            conditions.append({"field": _in_target, "operator": "eq", "value": _in_val})
                        _in_handled = True
                    break
                if _in_w in _CLAUSE_BREAKS or (_in_w in _CONDITION_TRIGGERS and _in_w != "with"):
                    break

            # --- Existing location-based handling (fallback) ---
            if not _in_handled:
                next_word = words[_in_start]
                field_match = _find_field_match(next_word, string_fields)

                if field_match and _in_start + 1 < len(words):
                    target = field_match
                    raw_val = words[_in_start + 1]
                elif next_word in location_hints and _in_start + 1 < len(words):
                    target = None
                    for f in string_fields:
                        fl = f.lower()
                        if fl == next_word or fl.endswith("." + next_word):
                            target = f
                            break
                    raw_val = words[_in_start + 1]
                else:
                    raw_val = next_word
                    target = None

                if not raw_val.isdigit():
                    value = raw_val.capitalize()

                    if target is None:
                        for hint in location_hints:
                            for f in string_fields:
                                fl = f.lower()
                                if fl == hint or fl.endswith("." + hint):
                                    target = f
                                    break
                            if target:
                                break
                        if target is None and string_fields:
                            target = string_fields[0]

                    if target:
                        conditions.append(
                            {"field": target, "operator": "eq", "value": value}
                        )

    # -------- ARRAY LITERAL CONDITIONS --------
    # If we extracted array literals, find the field before the placeholder
    # and create an eq condition with the actual list.
    for _ph, _arr_val in _array_literals.items():
        _ph_lower = _ph.lower()
        if _ph_lower in words:
            _ph_idx = words.index(_ph_lower)
            # Look backward for a field name (skip "as", "is", "=", etc.)
            _arr_field = None
            for _bi in range(_ph_idx - 1, max(_ph_idx - 5, -1), -1):
                if _bi < 0:
                    break
                _bw = words[_bi]
                if _bw in ("as", "is", "=", "equals", "equal", "being", ":"):
                    continue
                _arr_field = _find_field_match(_bw, allowed_fields)
                if _arr_field:
                    break
            if _arr_field and not any(c["field"] == _arr_field for c in conditions):
                conditions.append({"field": _arr_field, "operator": "eq", "value": _arr_val})
            # Remove placeholder from words so it doesn't interfere
            words = [w for w in words if w != _ph_lower]

    # -------- "where <field> is/= <value>" + implicit "<field> is <value>" --------

    def _parse_value(raw: str, field: str) -> Any:
        """Coerce *raw* to a numeric value.  Handles currency ($, \u20ac),
        commas (10,000), # prefix, and k/M/B suffixes ($10k \u2192 10000)."""
        val = _normalize_number(raw)
        if isinstance(val, (int, float)):
            return val
        return raw

    def _capture_multi_word_value(
        rest: List[str],
        start: int,
        field: str,
    ) -> Tuple[Any, int]:
        """Capture a multi-word value starting at *start* in *rest*.

        Stops at clause-break keywords, conjunctions introducing new
        conditions ("and <field>"), or field names that start a new condition.
        Returns ``(value, words_consumed)``.
        """
        parts: List[str] = []
        i = start
        while i < len(rest):
            w = rest[i]
            # Stop at clause breaks
            if w in _CLAUSE_BREAKS:
                break
            # Stop at condition triggers ONLY if followed by a field name
            # (to avoid breaking on trigger words inside natural values,
            #  e.g. "text is When faced with a challenge" — "with" is NOT
            #  followed by a field, so it's part of the value)
            if w in _CONDITION_TRIGGERS:
                if i + 1 < len(rest):
                    nxt = rest[i + 1]
                    if (_find_field_match(nxt, allowed_fields)
                            or _find_multi_word_field(rest, i + 1, allowed_fields)):
                        break
                else:
                    break  # trigger at end of input → stop
            # Stop at "and" if followed by a field name (new condition)
            if w in ("and", ",", "&"):
                if i + 1 < len(rest):
                    nxt = rest[i + 1]
                    if (_find_field_match(nxt, allowed_fields)
                            or _find_multi_word_field(rest, i + 1, allowed_fields)):
                        break
                # If "and" is in the middle of a value, keep going
                # but only if we already have some parts
                if parts:
                    parts.append(w)
                    i += 1
                    continue
                break
            parts.append(w)
            i += 1

        consumed = i - start
        if not parts:
            return None, 0

        raw_val = " ".join(parts)

        # Strip surrounding matched quotes (single or double)
        if len(raw_val) >= 2 and raw_val[0] == raw_val[-1] and raw_val[0] in ("'", '"'):
            raw_val = raw_val[1:-1]

        # Try number normalization (handles $, commas, k/M/B)
        num_val = _normalize_number(raw_val)
        if isinstance(num_val, (int, float)):
            return num_val, consumed

        return raw_val, consumed

    def _extract_condition(
        field_word: str,
        rest_words: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Given a candidate field word and remaining words, extract condition.

        Dynamically supports:
        - is / = / equals / being                  → eq (multi-word value)
        - not / != / isnt / isn't / except          → ne
        - contains / includes / like / matches      → contains (multi-word)
        - greater / more / above / > / after        → gt
        - >= / atleast                              → gte
        - less / fewer / below / < / before         → lt
        - <= / atmost                               → lte
        - between X and Y                           → gte + lte (range)
        - <numeric_value> (no operator, numeric)    → eq (implicit)
        - <string_value>  (no operator, string)     → eq (implicit, multi-word)
        """
        matched_field = _find_field_match(field_word, allowed_fields)
        if not matched_field:
            return None
        if not rest_words:
            return None

        op_word = rest_words[0]

        # --- "not" / negation before an operator: "is not X", "not X" ---
        negated = False
        effective_rest = rest_words

        if op_word in _OP_EQ and len(rest_words) >= 2 and rest_words[1] == "not":
            # "field is not X"
            negated = True
            effective_rest = rest_words[2:]  # skip "is" + "not"
            op_word = effective_rest[0] if effective_rest else ""
        elif op_word == "not" or op_word in _OP_NEQ:
            negated = True
            effective_rest = rest_words[1:]
            op_word = effective_rest[0] if effective_rest else ""

        # --- between X and Y ---
        if op_word == "between" and len(effective_rest) >= 4:
            try:
                lo = _parse_value(effective_rest[1], matched_field)
                # "between X and Y"
                and_idx = 2
                if effective_rest[2] == "and" and len(effective_rest) >= 4:
                    and_idx = 2
                    hi = _parse_value(effective_rest[3], matched_field)
                elif effective_rest[2] == "to" and len(effective_rest) >= 4:
                    and_idx = 2
                    hi = _parse_value(effective_rest[3], matched_field)
                else:
                    lo = _parse_value(effective_rest[1], matched_field)
                    hi = _parse_value(effective_rest[2], matched_field)
                return {
                    "field": matched_field, "operator": "between",
                    "value": [lo, hi],
                }
            except (ValueError, IndexError):
                pass

        # --- contains / includes / like / matches ---
        if op_word in _OP_CONTAINS:
            if len(effective_rest) >= 2:
                val, consumed = _capture_multi_word_value(
                    effective_rest, 1, matched_field,
                )
                if val is not None:
                    operator = "ne_contains" if negated else "contains"
                    # ne_contains not supported in MongoDB easily; use contains
                    return {
                        "field": matched_field,
                        "operator": "contains",
                        "value": val,
                    }

        # --- explicit eq: is / = / equals ---
        # But first check if "is" is followed by a comparison word
        # e.g. "date is after 2020" should become gt, not eq "after 2020"
        if op_word in _OP_EQ and len(effective_rest) >= 2:
            next_word = effective_rest[1]
            # If the next word is a comparison operator, redirect
            if next_word in _OP_GT:
                effective_rest = effective_rest[1:]
                op_word = next_word
                # Fall through to gt handler below
            elif next_word in _OP_GTE:
                effective_rest = effective_rest[1:]
                op_word = next_word
            elif next_word in _OP_LT:
                effective_rest = effective_rest[1:]
                op_word = next_word
            elif next_word in _OP_LTE:
                effective_rest = effective_rest[1:]
                op_word = next_word
            else:
                val, consumed = _capture_multi_word_value(
                    effective_rest, 1, matched_field,
                )
                if val is not None:
                    return {
                        "field": matched_field,
                        "operator": "ne" if negated else "eq",
                        "value": val,
                    }

        # --- gt / gte ---
        if op_word in _OP_GT:
            skip = 1
            if len(effective_rest) > 1 and effective_rest[1] in ("than", "to"):
                skip = 2
            # "greater than or equal to X" → gte
            if (len(effective_rest) > skip + 2
                    and effective_rest[skip] in ("or", "equal", "equals")
                    and effective_rest[skip + 1] in ("equal", "to", "equals")):
                skip += 2
                if len(effective_rest) > skip:
                    val = _parse_value(effective_rest[skip], matched_field)
                    return {"field": matched_field, "operator": "gte", "value": val}
            if len(effective_rest) > skip:
                val = _parse_value(effective_rest[skip], matched_field)
                return {"field": matched_field, "operator": "gt", "value": val}

        if op_word in _OP_GTE:
            skip = 1
            if len(effective_rest) > skip:
                val = _parse_value(effective_rest[skip], matched_field)
                return {"field": matched_field, "operator": "gte", "value": val}

        # --- lt / lte ---
        if op_word in _OP_LT:
            skip = 1
            if len(effective_rest) > 1 and effective_rest[1] in ("than", "to"):
                skip = 2
            # "less than or equal to X" → lte
            if (len(effective_rest) > skip + 2
                    and effective_rest[skip] in ("or", "equal", "equals")
                    and effective_rest[skip + 1] in ("equal", "to", "equals")):
                skip += 2
                if len(effective_rest) > skip:
                    val = _parse_value(effective_rest[skip], matched_field)
                    return {"field": matched_field, "operator": "lte", "value": val}
            if len(effective_rest) > skip:
                val = _parse_value(effective_rest[skip], matched_field)
                return {"field": matched_field, "operator": "lt", "value": val}

        if op_word in _OP_LTE:
            skip = 1
            if len(effective_rest) > skip:
                val = _parse_value(effective_rest[skip], matched_field)
                return {"field": matched_field, "operator": "lte", "value": val}

        # --- Implicit eq: numeric field followed by a number ---
        if matched_field in numeric_fields:
            # The rest_words[0] might be the value directly (no operator)
            val = _normalize_number(rest_words[0])
            if isinstance(val, (int, float)):
                return {
                    "field": matched_field,
                    "operator": "ne" if negated else "eq",
                    "value": val,
                }

        # --- Implicit eq for string fields: field followed by value(s) ---
        # Only if op_word is NOT a known keyword
        if (op_word not in _NOISE
                and op_word not in _CLAUSE_BREAKS
                and op_word not in _CONDITION_TRIGGERS
                and op_word not in ("and", ",", "&")):
            val, consumed = _capture_multi_word_value(
                rest_words, 0, matched_field,
            )
            if val is not None and consumed > 0:
                return {
                    "field": matched_field,
                    "operator": "ne" if negated else "eq",
                    "value": val,
                }

        return None

    def _count_condition_words(cond: Optional[Dict]) -> int:
        """Estimate how many words a condition consumed."""
        if not cond:
            return 0
        val = cond["value"]
        if isinstance(val, list):
            return 5  # between X and Y
        if isinstance(val, str):
            return 2 + len(val.split())  # field + op + value words
        return 3  # field + op + number

    # ================================================================
    # UNIFIED CONDITION SCANNING
    # ================================================================
    # Scans for conditions using all trigger keywords:
    #   where, with, having, whose, when, if, for, of, that, which
    # Each trigger starts a sub-scan that extracts field-operator-value
    # triplets.  Multiple triggers are tried (first "where", then others).
    # ================================================================

    def _scan_conditions_from(start_idx: int) -> None:
        """Scan words starting at *start_idx* and extract conditions."""
        i = start_idx
        while i < len(words):
            w = words[i]
            # conjunction / filler — skip
            if w in ("and", ",", "&", "the", "a", "an", "has", "have", "had"):
                i += 1
                continue
            # Try multi-word dot-notation first (e.g. "award tech")
            mw = _find_multi_word_field(words, i, allowed_fields)
            if mw:
                seg_count = len(mw.split("."))
                cond = _extract_condition(mw, words[i + seg_count:])
                if cond and not any(c["field"] == cond["field"] for c in conditions):
                    if cond["operator"] == "between":
                        # expand to gte + lte
                        conditions.append({"field": cond["field"], "operator": "gte", "value": cond["value"][0]})
                        conditions.append({"field": cond["field"], "operator": "lte", "value": cond["value"][1]})
                    else:
                        conditions.append(cond)
                i += seg_count + _count_condition_words(cond)
                continue
            # Try single word
            cond = _extract_condition(w, words[i + 1:])
            if cond and not any(c["field"] == cond["field"] for c in conditions):
                if cond["operator"] == "between":
                    conditions.append({"field": cond["field"], "operator": "gte", "value": cond["value"][0]})
                    conditions.append({"field": cond["field"], "operator": "lte", "value": cond["value"][1]})
                else:
                    conditions.append(cond)
                i += 1 + _count_condition_words(cond)
                continue

            # Fallback: try dot-joining consecutive words for fuzzy field matching
            _dj_found = False
            for _dj_k in range(min(4, len(words) - i), 1, -1):
                _dj_parts = words[i:i + _dj_k]
                if any(p in _OP_EQ | {"and", ",", "&"} | _OP_GT | _OP_LT
                       | {"than"} for p in _dj_parts[1:]):
                    continue
                _dj_candidate = ".".join(_dj_parts)
                _dj_cond = _extract_condition(_dj_candidate, words[i + _dj_k:])
                if _dj_cond and not any(c["field"] == _dj_cond["field"] for c in conditions):
                    if _dj_cond["operator"] == "between":
                        conditions.append({"field": _dj_cond["field"], "operator": "gte", "value": _dj_cond["value"][0]})
                        conditions.append({"field": _dj_cond["field"], "operator": "lte", "value": _dj_cond["value"][1]})
                    else:
                        conditions.append(_dj_cond)
                    i += _dj_k + _count_condition_words(_dj_cond)
                    _dj_found = True
                    break
            if _dj_found:
                continue

            # if this word is a clause break, stop
            if w in _CLAUSE_BREAKS:
                break
            i += 1

    # --- 1. Trigger-based condition scanning ---
    # Try each condition trigger keyword ("where", "with", "having", etc.)
    _all_triggers = ["where"] + [t for t in _CONDITION_TRIGGERS if t != "where"]
    # Also include "for" and "of" as lightweight triggers
    _all_triggers.extend(["for", "of"])
    _triggers_used = set()

    for trigger in _all_triggers:
        if trigger in _triggers_used:
            continue
        if trigger not in words:
            continue
        t_idx = words.index(trigger)
        _triggers_used.add(trigger)
        _scan_conditions_from(t_idx + 1)

    # --- 2. Multi-word implicit field matching (e.g. "options id is 123") ---
    _consumed_positions: set = set()
    for _mi in range(len(words)):
        if _mi in _consumed_positions:
            continue
        if words[_mi] in _NOISE:
            continue
        _mw_impl = _find_multi_word_field(words, _mi, allowed_fields)
        if _mw_impl:
            _seg_n = len(_mw_impl.split("."))
            _op_pos = _mi + _seg_n
            cond = _extract_condition(_mw_impl, words[_op_pos:])
            if cond and not any(c["field"] == _mw_impl for c in conditions):
                if cond["operator"] == "between":
                    conditions.append({"field": cond["field"], "operator": "gte", "value": cond["value"][0]})
                    conditions.append({"field": cond["field"], "operator": "lte", "value": cond["value"][1]})
                else:
                    conditions.append(cond)
                _consumed_positions.update(range(_mi, _op_pos + _count_condition_words(cond)))

    # --- 3. Implicit "<field> is/= <value>" (no trigger keyword) ---
    for field in allowed_fields:
        fl = field.lower()
        match_words = [fl]
        if "." in fl:
            match_words.append(fl.rsplit(".", 1)[-1])

        for mw in match_words:
            if mw in words:
                idx = words.index(mw)
                if idx in _consumed_positions:
                    break
                rest = words[idx + 1:]
                cond = _extract_condition(mw, rest)
                if cond and not any(c["field"] == field for c in conditions):
                    if cond["operator"] == "between":
                        conditions.append({"field": field, "operator": "gte", "value": cond["value"][0]})
                        conditions.append({"field": field, "operator": "lte", "value": cond["value"][1]})
                    else:
                        cond["field"] = field  # ensure full path
                        conditions.append(cond)
                break

    # --- 4. Standalone greater-than / less-than (field inferred) ---

    for i, w in enumerate(words):
        if w in COMPARISON_GT and i + 2 < len(words) and words[i + 1] == "than":
            val = _normalize_number(words[i + 2])
            if not isinstance(val, (int, float)):
                continue
            target = None
            for field in numeric_fields:
                if field.lower() in words:
                    target = field
                    break
                if "." in field:
                    last = field.rsplit(".", 1)[-1]
                    if last.lower() in words:
                        target = field
                        break
            if target is None and numeric_fields:
                age_like = [f for f in numeric_fields if f.lower() == "age"
                            or f.lower().endswith(".age")]
                target = age_like[0] if age_like else numeric_fields[0]
            if target and not any(
                c["field"] == target and c["operator"] in ("gt", "gte") for c in conditions
            ):
                conditions.append(
                    {"field": target, "operator": "gt", "value": val}
                )

        if w in COMPARISON_LT and i + 2 < len(words) and words[i + 1] == "than":
            val = _normalize_number(words[i + 2])
            if not isinstance(val, (int, float)):
                continue
            target = None
            for field in numeric_fields:
                if field.lower() in words:
                    target = field
                    break
                if "." in field:
                    last = field.rsplit(".", 1)[-1]
                    if last.lower() in words:
                        target = field
                        break
            if target is None and numeric_fields:
                age_like = [f for f in numeric_fields if f.lower() == "age"
                            or f.lower().endswith(".age")]
                target = age_like[0] if age_like else numeric_fields[0]
            if target and not any(
                c["field"] == target and c["operator"] in ("lt", "lte") for c in conditions
            ):
                conditions.append(
                    {"field": target, "operator": "lt", "value": val}
                )

    # --- 5. "over $500" / "under 100" without "than" ---
    for i, w in enumerate(words):
        if w in ("over", "above") and i + 1 < len(words) and words[i + 1] != "than":
            val = _normalize_number(words[i + 1])
            if isinstance(val, (int, float)):
                target = None
                for field in numeric_fields:
                    if field.lower() in words:
                        target = field
                        break
                    if "." in field and field.rsplit(".", 1)[-1].lower() in words:
                        target = field
                        break
                if target is None and numeric_fields:
                    target = numeric_fields[0]
                if target and not any(
                    c["field"] == target and c["operator"] in ("gt", "gte") for c in conditions
                ):
                    conditions.append({"field": target, "operator": "gt", "value": val})
        if w in ("under", "below") and i + 1 < len(words) and words[i + 1] != "than":
            val = _normalize_number(words[i + 1])
            if isinstance(val, (int, float)):
                target = None
                for field in numeric_fields:
                    if field.lower() in words:
                        target = field
                        break
                    if "." in field and field.rsplit(".", 1)[-1].lower() in words:
                        target = field
                        break
                if target is None and numeric_fields:
                    target = numeric_fields[0]
                if target and not any(
                    c["field"] == target and c["operator"] in ("lt", "lte") for c in conditions
                ):
                    conditions.append({"field": target, "operator": "lt", "value": val})

    # --- 6. Orphan numbers → pair with first unconditioned numeric field ---
    # Handles patterns like "show transaction #12345" or "order 42" where
    # the number value wasn't consumed by any condition scan.
    _has_numeric_cond = any(c["field"] in numeric_fields for c in conditions)
    if not _has_numeric_cond and numeric_fields:
        for _oi, _ow in enumerate(words):
            if _ow in _NOISE or _ow in _CLAUSE_BREAKS:
                continue
            # Skip if preceded by limit/sort words
            if _oi > 0 and words[_oi - 1] in ("top", "first", "limit"):
                continue
            val = _normalize_number(_ow)
            if isinstance(val, (int, float)):
                target = None
                for nf in numeric_fields:
                    if not any(c["field"] == nf for c in conditions):
                        target = nf
                        break
                if target:
                    conditions.append({"field": target, "operator": "eq", "value": val})
                break

    # -------- TEMPORAL CONDITIONS --------
    # Detect temporal expressions (today, yesterday, last month, etc.)
    # and apply them to date/time fields found in the schema.
    for _ti, _tw in enumerate(words):
        if _tw in _TEMPORAL_SINGLE or _tw in _TEMPORAL_MODIFIERS:
            trange, consumed = _build_temporal_range(words, _ti)
            if trange:
                # Find a date/time field in the schema
                _date_field = None
                _date_hints = ("date", "time", "created", "updated", "timestamp",
                               "hired", "joined", "started", "ended", "at",
                               "created_at", "updated_at", "ordered")
                for f in allowed_fields:
                    fl = f.lower()
                    if any(h in fl for h in _date_hints):
                        _date_field = f
                        break
                if _date_field:
                    if "gte" in trange and not any(
                        c["field"] == _date_field and c["operator"] == "gte"
                        for c in conditions
                    ):
                        conditions.append({"field": _date_field, "operator": "gte",
                                           "value": trange["gte"]})
                    if "lte" in trange and not any(
                        c["field"] == _date_field and c["operator"] == "lte"
                        for c in conditions
                    ):
                        conditions.append({"field": _date_field, "operator": "lte",
                                           "value": trange["lte"]})
                break  # only use first temporal expression

    # -------- SUPERLATIVE → SORT + LIMIT --------
    # "best seller" → sort desc + limit 1,  "top 5" → limit 5,
    # "lowest price" → sort asc + limit 1
    if sort is None:
        for _si, _sw in enumerate(words):
            if _sw in _SUPERLATIVE_DESC:
                _sup_dir = "desc"
            elif _sw in _SUPERLATIVE_ASC:
                _sup_dir = "asc"
            else:
                continue
            # "top N" / "best N"
            if _si + 1 < len(words):
                _sup_n = _normalize_number(words[_si + 1])
                if isinstance(_sup_n, int) and _sup_n > 0:
                    if limit is None:
                        limit = _sup_n
                    # Look for sort field after the number
                    if _si + 2 < len(words):
                        _sup_f = _find_field_match(words[_si + 2], allowed_fields)
                        if _sup_f:
                            sort = {"field": _sup_f, "direction": _sup_dir}
                    # Fallback: infer sort from numeric fields
                    if sort is None and numeric_fields:
                        sort = {"field": numeric_fields[0], "direction": _sup_dir}
                    break
            # "highest <field>" / "lowest <field>"
            if _si + 1 < len(words):
                _sup_f = _find_field_match(words[_si + 1], allowed_fields)
                if _sup_f:
                    sort = {"field": _sup_f, "direction": _sup_dir}
                    if limit is None:
                        limit = 1
                    break
            # No explicit field — infer from numeric fields
            if numeric_fields:
                sort = {"field": numeric_fields[0], "direction": _sup_dir}
                if limit is None:
                    limit = 1
                break

    # -------- QUESTION-WORD FIELD INFERENCE --------
    # "who" → project name/user/employee fields
    # "when" → project date/time fields
    # "where" → project location/city fields
    if projection is None and operation == "find":
        for _qw, _qhints in _QUESTION_FIELD_HINTS.items():
            if _qw not in words:
                continue
            _inferred: List[str] = []
            for hint in _qhints:
                for f in allowed_fields:
                    fl = f.lower()
                    if hint in fl or fl.endswith("." + hint):
                        if f not in _inferred:
                            _inferred.append(f)
                            break  # one match per hint
            if _inferred and len(_inferred) < len(allowed_fields):
                projection = _inferred
                break

    # -------- SORT --------

    for i, w in enumerate(words):
        if w in ("sorted", "sort", "order", "ordered"):
            if i + 2 < len(words) and words[i + 1] == "by":
                match = _find_field_match(words[i + 2], allowed_fields)
                if match:
                    direction = "asc"
                    if i + 3 < len(words) and words[i + 3] in (
                        "descending", "desc", "down",
                    ):
                        direction = "desc"
                    sort = {"field": match, "direction": direction}

    # If no explicit sort but "top/first N by <field>" was used, sort desc
    if sort is None:
        for i, w in enumerate(words):
            if w in ("top", "first") and i + 1 < len(words):
                # look for "by <field>" after the number
                for j in range(i + 2, min(i + 5, len(words))):
                    if words[j] == "by" and j + 1 < len(words):
                        match = _find_field_match(words[j + 1], allowed_fields)
                        if match:
                            sort = {"field": match, "direction": "desc"}
                        break

    # -------- LIMIT --------

    for i, w in enumerate(words):
        if w in ("limit", "top", "first") and i + 1 < len(words):
            try:
                limit = int(words[i + 1])
            except ValueError:
                pass
        # "N results / records / documents"
        try:
            n = int(w)
            if i + 1 < len(words) and words[i + 1] in (
                "results", "records", "documents", "docs", "rows",
            ):
                limit = n
        except ValueError:
            pass

    # -------- FINAL DECISION --------

    if operation == "aggregate" and aggregation is None:
        return None

    # allow bare "show all" / "list" with optional limit/sort
    if not conditions and operation == "find":
        has_show = any(w in SHOW_KEYWORDS for w in words)
        if not (has_show or limit is not None or sort is not None):
            return None

    # default cap for show-all find queries
    if limit is None and operation == "find" and not conditions:
        limit = 20

    return {
        "operation": operation,
        "conditions": conditions,
        "aggregation": aggregation,
        "sort": sort,
        "limit": limit,
        "projection": projection,
        "meta": {
            "confidence": 0.9 if (conditions or aggregation) else 0.6,
            "needs_clarification": False,
        },
    }
