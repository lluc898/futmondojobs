from config import CHAMPIONSHIP_ID, USERTEAM_ID
from utils.session import session, HEADERS

def obtener_jugadores(token):
    market_payload = {
        "header": {"token": token},
        "query": {
            "championshipId": CHAMPIONSHIP_ID,
            "userteamId": USERTEAM_ID,
            "type": "market"
        }
    }
    resp = session.post("https://api.futmondo.com/1/market/players", json=market_payload, headers=HEADERS)
    return resp.json().get("answer", [])

def filtrar_jugadores_positivos(jugadores):
    positivos = []
    for j in jugadores:
        if isinstance(j, dict) and j.get("change", 0) > 0:
            valor_actual = j.get("value", 0)
            cambio = j.get("change", 0)
            valor_anterior = valor_actual - cambio if valor_actual else 0
            porcentaje = (cambio / valor_anterior * 100) if valor_anterior else 0
            positivos.append({
                "nombre": j.get("name", ""),
                "equipo": j.get("team", ""),
                "valor_actual": valor_actual,
                "cambio": cambio,
                "porcentaje": porcentaje,
                "player_id": j.get("id", ""),
                "player_slug": j.get("slug", "")
            })
    positivos.sort(key=lambda x: x["porcentaje"], reverse=True)
    return positivos
