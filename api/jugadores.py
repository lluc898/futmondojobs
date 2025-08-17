from flask import Blueprint, jsonify
from services.jugadores_service import obtener_jugadores, filtrar_jugadores_positivos
from services.auth_service import login
from config import CHAMPIONSHIP_ID, USERTEAM_ID

jugadores_bp = Blueprint('jugadores', __name__)

@jugadores_bp.route('/jugadores/positivos', methods=['GET'])
def jugadores_positivos():
    credenciales, error = login()
    if error or not credenciales["token"]:
        return jsonify({"error": "No se pudo autenticar"}), 401
    jugadores = obtener_jugadores(credenciales["token"], credenciales["userid"])
    filtrados = filtrar_jugadores_positivos(jugadores)
    return jsonify(filtrados)
