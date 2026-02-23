"""
Legacy db.py — DEPRECATED.

All database operations now go through:
  - db_executor.py (query execution with pagination, projection, timeout)
  - schema_utils.py (schema sampling, caching, index inspection)
  - cluster_manager.py (cluster connect, list databases/collections)

This file is kept for backward compatibility but contains no active code.
"""

