

import requests
from data import MAIL, PWD, CHAMPIONSHIP_ID, USERTEAM_ID

session = requests.Session()




# Payload igual que la petición del navegador
payload = {
    "header": {
        "token": None,
        "userid": ""
    },
    "query": {
        "mail": MAIL,
        "pwd": PWD
    }
}



# Headers para simular un dispositivo móvil y mejorar autenticación
headers = {
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

# Endpoint correcto de login
login_url = "https://api.futmondo.com/5/login/with_mail"
login_resp = session.post(login_url, json=payload, headers=headers)
print("Status code:", login_resp.status_code)
print("Respuesta completa:", login_resp.text)
if login_resp.status_code == 200:
    print("Login correcto")
    login_data = login_resp.json()
    print("Datos de login:", login_data)
    # Extraer token y userid desde login_data['answer']['mobile']
    mobile = login_data.get("answer", {}).get("mobile", {})
    token = mobile.get("token")
    userid = mobile.get("userid")
    if not token or not userid:
        print("No se pudo obtener token o userid del login.")
    else:
        # Petición para obtener tus jugadores del mercado
        market_url = "https://api.futmondo.com/1/market/players"
        market_payload = {
            "header": {
                "token": token,
                "userid": userid
            },
            "query": {
                "championshipId": CHAMPIONSHIP_ID,
                "userteamId": USERTEAM_ID,
                "type": "market"
            }
        }
        market_headers = headers.copy()
        market_headers["Content-Type"] = "application/json; charset=utf-8"
        resp = session.post(market_url, json=market_payload, headers=market_headers)
        print("Jugadores del mercado:")
        print(resp.text)
else:
    print("Error en el login:", login_resp.text)