from config import CHAMPIONSHIP_ID, USERTEAM_ID
from utils.session import session, HEADERS

def realizar_puja(token, player_id, player_slug, price, is_clause, is_modify_bid):
    if is_modify_bid:
        bid_id = is_modify_bid
        payload = {
            "header": {
                "token": token,
                "userid": USERTEAM_ID
            },
            "query": {
                "bid": bid_id,
                "championshipId": CHAMPIONSHIP_ID,
                "userteamId": USERTEAM_ID,
                "player_id": player_id,
                "price": price,
                "isClause": is_clause,
                "rounds": []
            }
        }

        resp = session.post("https://api.futmondo.com/5/market/modifybid", json=payload, headers=HEADERS)
        return resp.json()
    
    else:
        payload = {
            "header": {
                "token": token
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
