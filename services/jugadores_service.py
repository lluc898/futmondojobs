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
    """Procesa y ordena TODOS los jugadores por cambio de valor (de mayor a menor).
    Ya no filtra solo positivos, devuelve todos ordenados por porcentaje descendente.
    """
    procesados = []
    for j in jugadores:
        if isinstance(j, dict):
            valor_actual = j.get("value", 0)
            cambio = j.get("change", 0)
            valor_anterior = valor_actual - cambio if valor_actual else 0
            porcentaje = (cambio / valor_anterior * 100) if valor_anterior else 0
            procesados.append({
                "nombre": j.get("name", ""),
                "equipo": j.get("team", ""),
                "valor_actual": valor_actual,
                "cambio": cambio,
                "porcentaje": porcentaje,
                "player_id": j.get("id", ""),
                "player_slug": j.get("slug", "")
            })
    # Ordenar de mayor a menor porcentaje (positivos primero, luego negativos)
    procesados.sort(key=lambda x: x["porcentaje"], reverse=True)
    return procesados

def obtener_informacion_userteam(token):
    """Obtiene información del userteam: presupuesto, puja máxima, pujas activas, etc."""
    payload = {
        "header": {"token": token},
        "query": {
            "championshipId": CHAMPIONSHIP_ID,
            "userteamId": USERTEAM_ID,
            "type": "market"
        }
    }
    resp = session.post("https://api.futmondo.com/1/userteam/information", json=payload, headers=HEADERS)
    data = resp.json()
    answer = data.get("answer", {})
    
    budget = answer.get("budget", 0)
    max_bid = answer.get("maxBid", 0)
    withheld = answer.get("withheld", 0)
    balance = budget - withheld
    
    return {
        "budget": budget,
        "max_bid": max_bid,
        "withheld": withheld,
        "balance": balance
    }
