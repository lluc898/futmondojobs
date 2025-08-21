
from config import MAIL, PWD
from utils.session import session, HEADERS
from utils.mongo import get_token, save_token
import requests
import time

def login():
    token, expires_at = get_token()
    now = int(time.time())
    if token and expires_at and expires_at > now:
        return {"token": token}, None

    payload = {
        "header": {"token": None},
        "query": {"mail": MAIL, "pwd": PWD}
    }
    resp = session.post("https://api.futmondo.com/5/login/with_mail", json=payload, headers=HEADERS)
    if resp.status_code != 200:
        return None, "Error en login"
    data = resp.json()
    mobile = data.get("answer", {}).get("mobile", {})
    token = mobile.get("token")
    # Guardar token y expiración (asumimos 1h de validez, ajustar si se sabe el tiempo real)
    expires_at = now + 3600
    save_token(token, expires_at)
    return {"token": token}, None

def get_token_doc():
    from utils.mongo import tokens_collection
    return tokens_collection.find_one({"_id": "login_token"})
