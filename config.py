import os
from dotenv import load_dotenv

load_dotenv()


def _get_pwd_env() -> str | None:
    # Preferir variables explícitas para evitar conflicto con PWD (working dir)
    for key in ("FUTMONDO_PWD", "FM_PWD", "FUTMONDO_PASSWORD", "PASSWORD"):
        val = os.getenv(key)
        if val:
            return val
    val = os.getenv("PWD")
    # Heurística: si parece una ruta del sistema, es el PWD del proceso, no el password
    if val and (val.startswith("/") or val.startswith("\\") or ":\\" in val or val == "/app"):
        return None
    return val


MAIL = os.getenv("MAIL")
PWD = _get_pwd_env()
CHAMPIONSHIP_ID = os.getenv("CHAMPIONSHIP_ID")
USERTEAM_ID = os.getenv("USERTEAM_ID")
MONGODB_URI = os.getenv("MONGODB_URI")
TOKEN_BOT = os.getenv("TOKEN")
USER_ID_TELEGRAM = int(os.getenv("USER_ID")) if os.getenv("USER_ID") else None
