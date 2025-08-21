import os
from dotenv import load_dotenv

load_dotenv()

MAIL = os.getenv("MAIL")
PWD = os.getenv("PWD")
CHAMPIONSHIP_ID = os.getenv("CHAMPIONSHIP_ID")
USERTEAM_ID = os.getenv("USERTEAM_ID")
MONGODB_URI = os.getenv("MONGODB_URI")
