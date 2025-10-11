import os
from dotenv import load_dotenv

load_dotenv()

MAIL = os.getenv("MAIL")
PWD = os.getenv("PWD")
CHAMPIONSHIP_ID = os.getenv("CHAMPIONSHIP_ID")
USERTEAM_ID = os.getenv("USERTEAM_ID")
MONGODB_URI = os.getenv("MONGODB_URI")
TOKEN_BOT = os.getenv("TOKEN")
USER_ID_TELEGRAM = int(os.getenv("USER_ID")) if os.getenv("USER_ID") else None
