from flask import Blueprint, request, jsonify
from services.bid_service import realizar_puja
from services.auth_service import login
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
    resultado = realizar_puja(credenciales["token"], player_id, player_slug, price, is_clause)
    return jsonify(resultado)
