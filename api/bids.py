from flask import Blueprint, request, jsonify
from services.bid_service import realizar_puja
from services.auth_service import login
from services.jugadores_service import obtener_jugadores
from config import CHAMPIONSHIP_ID, USERTEAM_ID

bids_bp = Blueprint('bids', __name__)

@bids_bp.route('/bid', methods=['POST'])
def bid():
    credenciales, error = login()
    if error or not credenciales["token"]:
        return jsonify({"error": "No se pudo autenticar"}), 401
    data = request.get_json()
    player_id = data.get("player_id")
    player_slug = data.get("player_slug")
    price = data.get("price")
    is_clause = data.get("isClause", False)
    if not all([player_id, player_slug, price]):
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    players = obtener_jugadores(credenciales["token"])
    players_dict = {p["id"]: p for p in players}
    try:
        is_modify_bid = players_dict.get(player_id).get("bid", False).get("id", False)
    except AttributeError:
        is_modify_bid = False

    resultado = realizar_puja(credenciales["token"], player_id, player_slug, price, is_clause, is_modify_bid)
    return jsonify(resultado)
