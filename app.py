from flask import Flask, jsonify
import requests
from data import MAIL, PWD, CHAMPIONSHIP_ID, USERTEAM_ID

app = Flask(__name__)
session = requests.Session()

HEADERS = {
    "Origin": "https://app.futmondo.com",
    "Referer": "https://app.futmondo.com/",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "es-ES,es;q=0.9",
    "X-Requested-With": "com.futmondo.app",
    "X-Device": "android",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site"
}

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

def obtener_jugadores(token, userid):
    market_payload = {
        "header": {"token": token, "userid": userid},
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
                "porcentaje": porcentaje
            })
    positivos.sort(key=lambda x: x["porcentaje"], reverse=True)
    return positivos

@app.route("/jugadores/positivos", methods=["GET"])
def jugadores_positivos():
    credenciales, error = login()
    if error or not credenciales["token"]:
        return jsonify({"error": "No se pudo autenticar"}), 401
    
    jugadores = obtener_jugadores(credenciales["token"], credenciales["userid"])
    filtrados = filtrar_jugadores_positivos(jugadores)
    return jsonify(filtrados)

if __name__ == "__main__":
    app.run(debug=True)