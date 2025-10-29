from config import MAIL, PWD
from utils.session import session, HEADERS
from utils.mongo import get_token, save_token
import requests
import time
import logging
import os
import socket


def login():
    # Validaciones básicas de entorno
    if not MAIL or not PWD:
        logging.warning("Login: faltan variables MAIL o PWD en el entorno del contenedor")
        return None, "Faltan MAIL o PWD en variables de entorno"

    token, expires_at = get_token()
    now = int(time.time())
    # if token and expires_at and expires_at > now:
    #     return {"token": token}, None

    payload = {
        "header": {
            "token": None,
            "device": "android",
            "deviceId": os.getenv("DEVICE_ID", f"docker-{socket.gethostname()}"),
            "lang": "es",
        },
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
        logging.exception("Login: error de red haciendo request a Futmondo")
        return None, f"Error de red en login: {e}"

    if resp.status_code != 200:
        try:
            body = resp.text
        except Exception:
            body = "<sin cuerpo>"
        logging.warning("Login: respuesta HTTP no 200: %s, body: %s", resp.status_code, body[:300])
        return None, f"Error en login HTTP {resp.status_code}: {body[:200]}"

    try:
        data = resp.json()
    except Exception:
        logging.warning("Login: la respuesta de Futmondo no es JSON")
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
        try:
            logging.warning(
                "Login: respuesta sin token. Mensaje: %s; keys=%s; answer=%s; payload=%s; headers-UA=%s",
                msg,
                list(data.keys()),
                str(data.get("answer"))[:400],
                str(payload)[:300],
                HEADERS.get("User-Agent"),
            )
        except Exception:
            logging.warning("Login: respuesta sin token y no se pudo serializar el body")
        return None, msg

    # Guardar token y expiración (asumimos 1h de validez)
    expires_at = now + 3600
    try:
        save_token(token, expires_at)
        logging.info("Login: token obtenido y guardado en cache")
    except Exception:
        logging.exception("Login: no se pudo guardar el token en MongoDB (no bloqueante)")

    return {"token": token}, None


def get_token_doc():
    from utils.mongo import tokens_collection
    return tokens_collection.find_one({"_id": "login_token"})
