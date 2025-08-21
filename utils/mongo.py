from pymongo import MongoClient
from config import MONGODB_URI

client = MongoClient(MONGODB_URI)
db = client.get_database()

tokens_collection = db.tokens

# Helper to get token from DB
def get_token():
    doc = tokens_collection.find_one({"_id": "login_token"})
    if doc:
        return doc.get("token"), doc.get("expires_at")
    return None, None

# Helper to save token in DB
def save_token(token, expires_at):
    tokens_collection.update_one(
        {"_id": "login_token"},
        {"$set": {"token": token, "expires_at": expires_at}},
        upsert=True
    )
