from config import MAIL, PWD
from utils.session import session, HEADERS
from utils.mongo import get_token, save_token
import requests
import time
import logging


def login():
    # Validaciones básicas de entorno
    if not MAIL or not PWD:
        return None, "Faltan MAIL o PWD en variables de entorno"

    token, expires_at = get_token()
    now = int(time.time())
    # if token and expires_at and expires_at > now:
    #     return {"token": token}, None

    payload = {
        "header": {"token": None},
        "query": {"mail": MAIL, "pwd": PWD}
    }

    try:
        resp = session.post(
            "https://api.futmondo.com/5/login/with_mail",
            json=payload,
            headers=HEADERS,
            timeout=20,
        )
    except Exception as e:
        logging.exception("Error haciendo login contra Futmondo")
        return None, f"Error de red en login: {e}"

    if resp.status_code != 200:
        try:
            body = resp.text
        except Exception:
            body = "<sin cuerpo>"
        return None, f"Error en login HTTP {resp.status_code}: {body[:200]}"

    try:
        data = resp.json()
    except Exception:
        return None, "Respuesta de login no es JSON"

    mobile = data.get("answer", {}).get("mobile", {})
    token = mobile.get("token")
    if not token:
        msg = (
            data.get("error")
            or data.get("message")
            or data.get("answer", {}).get("message")
            or "Login sin token"
        )
        return None, msg

    # Guardar token y expiración (asumimos 1h de validez)
    expires_at = now + 3600
    try:
        save_token(token, expires_at)
    except Exception:
        logging.exception("No se pudo guardar el token en MongoDB")

    return {"token": token}, None


def get_token_doc():
    from utils.mongo import tokens_collection
    return tokens_collection.find_one({"_id": "login_token"})

