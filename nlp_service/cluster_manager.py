from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

SERVER_TIMEOUT_MS = 5000


def connect_to_cluster(mongo_uri: str):
    """Create and test a MongoClient connection."""
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=SERVER_TIMEOUT_MS)
        client.server_info()  # force connection test
        return client
    except ServerSelectionTimeoutError:
        raise Exception("Connection timed out. Check your MongoDB URI and network.")
    except ConnectionFailure:
        raise Exception("Failed to connect to MongoDB cluster")


def list_databases(mongo_uri: str):
    client = connect_to_cluster(mongo_uri)
    try:
        dbs = client.list_database_names()
        return {
            "total_databases": len(dbs),
            "databases": dbs,
        }
    finally:
        client.close()


def list_collections(mongo_uri: str, database_name: str):
    """List collections with estimated doc counts (avoids full scans)."""
    client = connect_to_cluster(mongo_uri)
    try:
        db = client[database_name]
        collections_info = []

        for col_name in db.list_collection_names():
            try:
                count = db[col_name].estimated_document_count()
            except Exception:
                count = 0
            collections_info.append({
                "name": col_name,
                "document_count": count,
            })

        return collections_info
    finally:
        client.close()