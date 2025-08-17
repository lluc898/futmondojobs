from config import MAIL, PWD
from utils.session import session, HEADERS
import requests

def login():
    payload = {
        "header": {"token": None, "userid": ""},
        "query": {"mail": MAIL, "pwd": PWD}
    }
    resp = session.post("https://api.futmondo.com/5/login/with_mail", json=payload, headers=HEADERS)
    if resp.status_code != 200:
        return None, "Error en login"
    data = resp.json()
    mobile = data.get("answer", {}).get("mobile", {})
    return {
        "token": mobile.get("token"),
        "userid": mobile.get("userid")
    }, None
