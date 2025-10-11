import asyncio
from flask import Blueprint, jsonify
from telegram import Bot
from services.jugadores_service import obtener_jugadores, filtrar_jugadores_positivos
from services.auth_service import login
from config import TOKEN_BOT as TOKEN, USER_ID_TELEGRAM as USER_ID

send_bp = Blueprint('send', __name__)

# Coloca tu token y tu user ID aquí
# token and user_id should be set in config or environment variables

def format_player_message(player):
    nombre = player.get('nombre', 'Desconocido')
    equipo = player.get('equipo', '—')
    valor_actual = player.get('valor_actual', '—')
    cambio = player.get('cambio', '—')
    porcentaje = player.get('porcentaje', 0)

    try:
        porcentaje_text = f"{porcentaje:.2f}%"
    except Exception:
        porcentaje_text = f"{porcentaje}%"

    return (
        "🔥 <b>Jugador en tendencia</b>\n"
        f"👤 <b>{nombre}</b>\n"
        f"🏟️ <i>{equipo}</i>\n"
        f"💰 Valor actual: <b>{valor_actual}</b>\n"
        f"📈 Cambio: <b>+{cambio}</b> (<b>+{porcentaje_text}</b>)"
    )

async def send_message():
    token_telegram = TOKEN
    bot = Bot(token=token_telegram)
    credenciales, error = login()
    if error or not credenciales["token"]:
        print("No se pudo autenticar")
        return
    # Obtener jugadores disponibles
    available_players = obtener_jugadores(credenciales["token"])
    # Filtrar jugadores positivos
    positive_players = filtrar_jugadores_positivos(available_players)

    if not positive_players:
        user_telegram = USER_ID
        await bot.send_message(
            chat_id=user_telegram,
            text="😴 No hay jugadores con cambios positivos en este momento.",
            parse_mode="HTML",
        )
        return

    # Enviar cada jugador en un mensaje separado
    for player in positive_players:
        message_text = format_player_message(player)
        try:
            await bot.send_message(chat_id=USER_ID, text=message_text, parse_mode="HTML")
        except Exception as e:
            # Log simple para continuar con los demás
            print(f"Error enviando jugador {player.get('nombre')}: {e}")
        await asyncio.sleep(0.5)  # pequeña pausa para evitar rate limits

@send_bp.route('/send', methods=['POST'])
def trigger_send_message():
    asyncio.run(send_message())
    return "Mensaje enviado", 200