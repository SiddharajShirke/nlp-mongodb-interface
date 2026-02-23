"""
IR validator: validates parsed IR against the actual collection schema.

Supports:
- Dynamic allowed_fields (including dot-notation nested fields)
- Schema-aware field resolution (e.g. ``city`` → ``address.city``)
- Fuzzy matching for typos (difflib, threshold 0.8)
- Operator allow-list
- Hard limit cap
- Projection field validation
- Helpful "did you mean?" suggestions for typos
"""

from typing import Any, Dict, List, Optional
from difflib import get_close_matches, SequenceMatcher

from logger import logger

ALLOWED_OPERATORS = ["eq", "gt", "lt", "gte", "lte", "in", "ne", "exists", "contains"]
MAX_LIMIT = 100


# ---------------------- FIELD RESOLUTION ----------------------


def resolve_field_name(user_field: str, allowed_fields: List[str]) -> Optional[str]:
    """Resolve a user-supplied field name against the collection schema.

    Resolution strategy (in priority order):
    1. **Exact match** (case-insensitive).
    2. **Dot-suffix match** — ``user_field`` matches the last segment of a
       dot-notation field (e.g. ``city`` → ``address.city``).
       - If exactly one match  → return it.
       - If multiple matches   → return the first (log ambiguity warning).
    3. **Multi-segment fuzzy** — user typed ``adress.city`` → fuzzy-compare
       each segment against allowed fields (threshold 0.8).
    4. **Single-token fuzzy** — fuzzy match ``user_field`` against full field
       names and their last segments (threshold 0.8).
    5. No match → return ``None``.

    Debug logging is emitted for every resolution attempt.
    """
    uf = user_field.strip()
    uf_lower = uf.lower()

    logger.info("resolve_field_name — User field: '%s'", uf)
    logger.info("resolve_field_name — Allowed fields: %s", allowed_fields)

    # 1. Exact match (case-insensitive)
    for af in allowed_fields:
        if af.lower() == uf_lower:
            logger.info("resolve_field_name — Exact match: '%s' → '%s'", uf, af)
            return af

    # 1b. Space-separated tokens → dot-notation (e.g. "options id" → "options.id")
    if " " in uf:
        dot_joined = uf.replace(" ", ".")
        result = resolve_field_name(dot_joined, allowed_fields)
        if result is not None:
            logger.info(
                "resolve_field_name — Space→dot: '%s' → '%s'", uf, result,
            )
            return result

    # 2. Dot-suffix / last-segment match
    suffix_matches: List[str] = []
    for af in allowed_fields:
        if "." in af:
            last_segment = af.rsplit(".", 1)[-1]
            if last_segment.lower() == uf_lower:
                suffix_matches.append(af)

    if len(suffix_matches) == 1:
        logger.info(
            "resolve_field_name — Unique suffix match: '%s' → '%s'",
            uf, suffix_matches[0],
        )
        return suffix_matches[0]

    if len(suffix_matches) > 1:
        logger.warning(
            "resolve_field_name — Ambiguous suffix match for '%s': %s  "
            "(returning first match '%s')",
            uf, suffix_matches, suffix_matches[0],
        )
        return suffix_matches[0]

    # 3. Multi-segment fuzzy (user typed dot-notation with typos)
    if "." in uf_lower:
        user_segments = uf_lower.split(".")
        best_field: Optional[str] = None
        best_avg_score = 0.0

        for af in allowed_fields:
            if "." not in af:
                continue
            af_segments = af.lower().split(".")
            if len(user_segments) != len(af_segments):
                continue
            scores = [
                SequenceMatcher(None, us, fs).ratio()
                for us, fs in zip(user_segments, af_segments)
            ]
            avg = sum(scores) / len(scores)
            if avg >= 0.80 and avg > best_avg_score:
                best_avg_score = avg
                best_field = af

        if best_field is not None:
            logger.info(
                "resolve_field_name — Multi-segment fuzzy: '%s' → '%s' (score %.2f)",
                uf, best_field, best_avg_score,
            )
            return best_field

    # 4. Single-token fuzzy against full names + last segments
    candidates: List[str] = list(allowed_fields)
    # map lowered candidate → original allowed field
    candidate_map: Dict[str, str] = {}
    for af in allowed_fields:
        candidate_map[af.lower()] = af
        if "." in af:
            seg = af.rsplit(".", 1)[-1].lower()
            # only overwrite if not already present (prefer full path)
            if seg not in candidate_map:
                candidate_map[seg] = af

    close = get_close_matches(
        uf_lower,
        list(candidate_map.keys()),
        n=1,
        cutoff=0.80,
    )
    if close:
        resolved = candidate_map[close[0]]
        logger.info(
            "resolve_field_name — Fuzzy match: '%s' → '%s' (matched '%s')",
            uf, resolved, close[0],
        )
        return resolved

    logger.info("resolve_field_name — No match for '%s'", uf)
    return None


# ---------------------- HELPERS ----------------------


def _suggest_field(field: str, allowed_fields: List[str]) -> str:
    """Return a 'did you mean?' hint for an invalid field."""
    candidates = list(allowed_fields)
    for f in allowed_fields:
        if "." in f:
            candidates.append(f.rsplit(".", 1)[-1])
    matches = get_close_matches(
        field.lower(), [c.lower() for c in candidates], n=3, cutoff=0.5,
    )
    if matches:
        suggestions: List[str] = []
        for m in matches:
            for af in allowed_fields:
                if af.lower() == m or (
                    "." in af and af.rsplit(".", 1)[-1].lower() == m
                ):
                    if af not in suggestions:
                        suggestions.append(af)
        if suggestions:
            return f" Did you mean: {', '.join(suggestions)}?"
    return ""


# ---------------------- MAIN VALIDATOR ----------------------


def validate_ir(ir: Dict[str, Any], allowed_fields: List[str]) -> Dict[str, Any]:
    """Validate an IR dict against the collection schema.

    For every field reference (conditions, aggregation, sort, projection)
    the validator first attempts to **resolve** the raw field name to a
    full dot-notation path via ``resolve_field_name``.  If resolution
    succeeds the field is silently rewritten in the IR so that downstream
    compilation and execution work against the correct MongoDB path.

    Raises ``ValueError`` on unresolvable fields or disallowed operators.
    Enforces ``MAX_LIMIT`` cap on results.
    """

    # --- Resolve & validate condition fields ---
    for condition in ir.get("conditions", []):
        raw_field = condition["field"]
        operator = condition["operator"]

        resolved = resolve_field_name(raw_field, allowed_fields)
        if resolved is None:
            hint = _suggest_field(raw_field, allowed_fields)
            raise ValueError(
                f"Field '{raw_field}' not found in collection.{hint}"
            )
        # Overwrite with resolved full path
        condition["field"] = resolved

        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f"Operator '{operator}' not allowed")

    # --- Resolve & validate aggregation field ---
    agg = ir.get("aggregation")
    if agg and agg.get("field"):
        raw_field = agg["field"]
        resolved = resolve_field_name(raw_field, allowed_fields)
        if resolved is None:
            hint = _suggest_field(raw_field, allowed_fields)
            raise ValueError(
                f"Aggregation field '{raw_field}' not found in collection.{hint}"
            )
        agg["field"] = resolved

    # --- Resolve & validate sort field ---
    sort = ir.get("sort")
    if sort and sort.get("field"):
        raw_field = sort["field"]
        resolved = resolve_field_name(raw_field, allowed_fields)
        if resolved is None:
            hint = _suggest_field(raw_field, allowed_fields)
            raise ValueError(
                f"Sort field '{raw_field}' not found in collection.{hint}"
            )
        sort["field"] = resolved

    # --- Resolve & validate projection fields ---
    projection = ir.get("projection")
    if projection:
        resolved_projection: List[str] = []
        for pf in projection:
            resolved = resolve_field_name(pf, allowed_fields)
            if resolved is None:
                hint = _suggest_field(pf, allowed_fields)
                raise ValueError(
                    f"Projection field '{pf}' not found in collection.{hint}"
                )
            resolved_projection.append(resolved)
        ir["projection"] = resolved_projection

    # --- Enforce hard limit cap ---
    if ir.get("limit") is not None:
        if ir["limit"] > MAX_LIMIT:
            ir["limit"] = MAX_LIMIT

    return ir