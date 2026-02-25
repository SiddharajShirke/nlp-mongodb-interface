"""
Activity Tracker — persists every query, diagnosis, and mutation commit
into a ``_nlp_activity`` collection inside the user's connected database.

Each activity document is lightweight (~0.5 KB) and indexed by timestamp,
so dashboard analytics stay fast even on large collections.

Collections used:
    _nlp_activity       — one doc per query / diagnose / commit event
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError

from logger import logger

# ─── Constants ────────────────────────────────────────────────────────
ACTIVITY_COLLECTION = "_nlp_activity"
_CLIENT_TIMEOUT_MS = 5000


# ─── Activity Types ──────────────────────────────────────────────────
ACTIVITY_QUERY = "query"
ACTIVITY_DIAGNOSE = "diagnose"
ACTIVITY_COMMIT = "commit"


# ─── Helpers ─────────────────────────────────────────────────────────

def _get_collection(mongo_uri: str, database_name: str):
    """Return a reference to the _nlp_activity collection."""
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=_CLIENT_TIMEOUT_MS)
    db = client[database_name]
    return client, db[ACTIVITY_COLLECTION]


def _ensure_indexes(coll) -> None:
    """Create indexes on first write (idempotent)."""
    try:
        existing = {idx["name"] for idx in coll.list_indexes()}
        if "ts_desc" not in existing:
            coll.create_index([("timestamp", DESCENDING)], name="ts_desc")
        if "type_ts" not in existing:
            coll.create_index(
                [("activity_type", 1), ("timestamp", DESCENDING)],
                name="type_ts",
            )
        if "user_ts" not in existing:
            coll.create_index(
                [("user_email", 1), ("timestamp", DESCENDING)],
                name="user_ts",
            )
    except PyMongoError:
        pass  # non-critical


# ─── Write ───────────────────────────────────────────────────────────

def log_activity(
    mongo_uri: str,
    database_name: str,
    *,
    activity_type: str,
    collection_name: str = "",
    user_email: str = "anonymous",
    query: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Fire-and-forget — logs the event, never raises."""
    client = None
    try:
        client, coll = _get_collection(mongo_uri, database_name)
        _ensure_indexes(coll)
        doc = {
            "activity_type": activity_type,
            "collection_name": collection_name,
            "user_email": user_email,
            "query": query,
            "timestamp": datetime.now(timezone.utc),
            "details": details or {},
        }
        coll.insert_one(doc)
        logger.debug("[ACTIVITY] Logged %s for %s", activity_type, user_email)
    except Exception as e:
        logger.warning("[ACTIVITY] Failed to log: %s", e)
    finally:
        if client:
            client.close()


# ─── Shared time helpers ─────────────────────────────────────────────

def _build_time_filter(
    *,
    lookback_minutes: Optional[int] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a ``timestamp`` filter sub-document from the caller's params.

    Priority:
      1. lookback_minutes  → sliding window ("last N minutes")
      2. year/month/day    → absolute calendar range
    """
    from datetime import timedelta

    if lookback_minutes and lookback_minutes > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        return {"$gte": cutoff}

    if year:
        start = datetime(year, month or 1, day or 1, tzinfo=timezone.utc)
        if day:
            end = start + timedelta(days=1)
        elif month:
            if month == 12:
                end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        return {"$gte": start, "$lt": end}

    return {}


def _resolve_granularity(
    granularity: str = "auto",
    lookback_minutes: Optional[int] = None,
) -> str:
    """Pick the date-format string for ``$dateToString`` aggregation.

    auto rules:
        <=  120 min   → minute   (%Y-%m-%d %H:%M)
        <=  72 hours  → hour     (%Y-%m-%d %H:00)
        <=  90 days   → day      (%Y-%m-%d)
        >   90 days   → month    (%Y-%m)
    """
    FORMAT_MAP = {
        "minute": "%Y-%m-%d %H:%M",
        "hour":   "%Y-%m-%d %H:00",
        "day":    "%Y-%m-%d",
        "month":  "%Y-%m",
    }
    if granularity != "auto" and granularity in FORMAT_MAP:
        return FORMAT_MAP[granularity]

    if lookback_minutes is None:
        return FORMAT_MAP["day"]

    if lookback_minutes <= 120:
        return FORMAT_MAP["minute"]
    if lookback_minutes <= 72 * 60:
        return FORMAT_MAP["hour"]
    if lookback_minutes <= 90 * 24 * 60:
        return FORMAT_MAP["day"]
    return FORMAT_MAP["month"]


# ─── Read — Commit Timeline ─────────────────────────────────────────

def get_commit_timeline(
    mongo_uri: str,
    database_name: str,
    *,
    user_email: Optional[str] = None,
    lookback_minutes: Optional[int] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Return recent commit events, newest-first."""
    client = None
    try:
        client, coll = _get_collection(mongo_uri, database_name)
        filt: Dict[str, Any] = {"activity_type": ACTIVITY_COMMIT}
        if user_email:
            filt["user_email"] = user_email
        ts_filt = _build_time_filter(lookback_minutes=lookback_minutes)
        if ts_filt:
            filt["timestamp"] = ts_filt

        docs = list(
            coll.find(filt, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
        for d in docs:
            if "timestamp" in d:
                d["timestamp"] = d["timestamp"].isoformat()
        return docs
    except Exception as e:
        logger.warning("[ACTIVITY] get_commit_timeline failed: %s", e)
        return []
    finally:
        if client:
            client.close()


# ─── Read — Aggregated Stats ────────────────────────────────────────

def get_activity_stats(
    mongo_uri: str,
    database_name: str,
    *,
    user_email: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    lookback_minutes: Optional[int] = None,
    granularity: str = "auto",
) -> Dict[str, Any]:
    """Aggregate activity counts grouped by type and by time bucket.

    Returns:
        {
          "totals": { "query": N, "diagnose": N, "commit": N },
          "timeline": [
              { "bucket": "2026-02-25 14:00", "query": 5, ... },
              ...
          ],
          "severity": { "ok": N, "error": N, "warning": N },
          "top_collections": [ { "name": "...", "count": N }, ... ],
          "granularity": "hour",
        }
    """
    client = None
    try:
        client, coll = _get_collection(mongo_uri, database_name)

        # Base filter
        base_filt: Dict[str, Any] = {}
        if user_email:
            base_filt["user_email"] = user_email
        ts_filt = _build_time_filter(
            lookback_minutes=lookback_minutes, year=year, month=month, day=day,
        )
        if ts_filt:
            base_filt["timestamp"] = ts_filt

        date_fmt = _resolve_granularity(granularity, lookback_minutes)

        # 1) Totals by type
        type_pipeline = [
            {"$match": base_filt},
            {"$group": {"_id": "$activity_type", "count": {"$sum": 1}}},
        ]
        type_results = list(coll.aggregate(type_pipeline))
        totals = {r["_id"]: r["count"] for r in type_results}

        # 2) Timeline breakdown by chosen granularity
        timeline_pipeline = [
            {"$match": base_filt},
            {
                "$group": {
                    "_id": {
                        "bucket": {
                            "$dateToString": {"format": date_fmt, "date": "$timestamp"}
                        },
                        "type": "$activity_type",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.bucket": 1}},
        ]
        timeline_raw = list(coll.aggregate(timeline_pipeline))

        # Pivot into { bucket, query, diagnose, commit }
        timeline_map: Dict[str, Dict[str, Any]] = {}
        for row in timeline_raw:
            bucket = row["_id"]["bucket"]
            atype = row["_id"]["type"]
            if bucket not in timeline_map:
                timeline_map[bucket] = {"bucket": bucket, "query": 0, "diagnose": 0, "commit": 0}
            timeline_map[bucket][atype] = row["count"]
        timeline = sorted(timeline_map.values(), key=lambda x: x["bucket"])

        # 3) Diagnosis severity
        sev_filt = {**base_filt, "activity_type": ACTIVITY_DIAGNOSE}
        sev_pipeline = [
            {"$match": sev_filt},
            {"$group": {"_id": "$details.severity", "count": {"$sum": 1}}},
        ]
        sev_raw = list(coll.aggregate(sev_pipeline))
        severity = {(r["_id"] or "unknown"): r["count"] for r in sev_raw}

        # 4) Top collections
        top_pipeline = [
            {"$match": base_filt},
            {"$group": {"_id": "$collection_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        top_raw = list(coll.aggregate(top_pipeline))
        top_collections = [{"name": r["_id"], "count": r["count"]} for r in top_raw if r["_id"]]

        # Determine label for the frontend
        gran_label = "auto"
        for g in ("minute", "hour", "day", "month"):
            if _resolve_granularity(g) == date_fmt:
                gran_label = g
                break

        return {
            "totals": totals,
            "timeline": timeline,
            "severity": severity,
            "top_collections": top_collections,
            "granularity": gran_label,
        }
    except Exception as e:
        logger.warning("[ACTIVITY] get_activity_stats failed: %s", e)
        return {"totals": {}, "timeline": [], "severity": {}, "top_collections": [], "granularity": "day"}
    finally:
        if client:
            client.close()


# ─── Read — Diagnosis scores per period ──────────────────────────────

def get_diagnosis_monthly(
    mongo_uri: str,
    database_name: str,
    *,
    user_email: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    granularity: str = "auto",
) -> List[Dict[str, Any]]:
    """Aggregate diagnosis events by time bucket with severity breakdown.

    Returns list of:
        {
            "bucket": "2026-01" | "2026-01-15" | "2026-01-15 14:00",
            "total": 15, "ok": 10, "error": 3, "warning": 2,
            "score": 66.7,
        }
    """
    client = None
    try:
        client, coll = _get_collection(mongo_uri, database_name)

        filt: Dict[str, Any] = {"activity_type": ACTIVITY_DIAGNOSE}
        if user_email:
            filt["user_email"] = user_email
        ts_filt = _build_time_filter(year=year, month=month, day=day)
        if ts_filt:
            filt["timestamp"] = ts_filt

        # If granularity is auto, pick based on the range
        if granularity == "auto":
            if day:
                date_fmt = _resolve_granularity("hour")
            elif month:
                date_fmt = _resolve_granularity("day")
            else:
                date_fmt = _resolve_granularity("month")
        else:
            date_fmt = _resolve_granularity(granularity)

        pipeline = [
            {"$match": filt},
            {
                "$group": {
                    "_id": {
                        "bucket": {
                            "$dateToString": {"format": date_fmt, "date": "$timestamp"}
                        },
                        "severity": "$details.severity",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.bucket": 1}},
        ]
        raw = list(coll.aggregate(pipeline))

        bucket_map: Dict[str, Dict[str, Any]] = {}
        for row in raw:
            b = row["_id"]["bucket"]
            sev = row["_id"].get("severity") or "unknown"
            if b not in bucket_map:
                bucket_map[b] = {"bucket": b, "total": 0, "ok": 0, "error": 0, "warning": 0}
            bucket_map[b][sev] = bucket_map[b].get(sev, 0) + row["count"]
            bucket_map[b]["total"] += row["count"]

        result = sorted(bucket_map.values(), key=lambda x: x["bucket"])
        for item in result:
            total = item["total"]
            item["score"] = round(item["ok"] / total * 100, 1) if total > 0 else 0
        return result
    except Exception as e:
        logger.warning("[ACTIVITY] get_diagnosis_monthly failed: %s", e)
        return []
    finally:
        if client:
            client.close()
