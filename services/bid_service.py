from config import CHAMPIONSHIP_ID, USERTEAM_ID
from utils.session import session, HEADERS

def realizar_puja(token, userid, player_id, player_slug, price, is_clause):
    payload = {
        "header": {
            "token": token,
            "userid": userid
        },
        "query": {
            "championshipId": CHAMPIONSHIP_ID,
            "userteamId": USERTEAM_ID,
            "player_id": player_id,
            "player_slug": player_slug,
            "price": price,
            "isClause": is_clause
        }
    }
    resp = session.post("https://api.futmondo.com/1/market/bid", json=payload, headers=HEADERS)
    return resp.json()
