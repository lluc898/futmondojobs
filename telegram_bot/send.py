import asyncio
from flask import Blueprint, jsonify, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
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
        player_id = player.get("player_id")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Pujar +5%", callback_data=f"bid|{player_id}|5"),
                InlineKeyboardButton("Pujar +10%", callback_data=f"bid|{player_id}|10"),
                InlineKeyboardButton("Pujar +15%", callback_data=f"bid|{player_id}|15"),
            ]
        ])
        try:
            await bot.send_message(
                chat_id=USER_ID,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e:
            # Log simple para continuar con los demás
            print(f"Error enviando jugador {player.get('nombre')}: {e}")
        await asyncio.sleep(0.5)  # pequeña pausa para evitar rate limits

@send_bp.route('/send', methods=['POST'])
def trigger_send_message():
    asyncio.run(send_message())
    return "Mensaje enviado", 200


@send_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Webhook para procesar callbacks de Telegram y realizar pujas."""
    # update_print = request.json
    # print(update_print)
    try:
        token_telegram = TOKEN
        if not token_telegram:
            return jsonify({"ok": False, "error": "Falta TOKEN"}), 500

        bot = Bot(token=token_telegram)
        update = Update.de_json(request.get_json(force=True, silent=True) or {}, bot)
        if not update:
            return jsonify({"ok": True})

        if update.callback_query:
            cq = update.callback_query
            # Seguridad opcional: solo aceptar del usuario configurado
            if USER_ID and cq.from_user and cq.from_user.id != USER_ID:
                try:
                    cq.answer(text="No autorizado", show_alert=True)
                except Exception:
                    pass
                return jsonify({"ok": True})

            data = (cq.data or "")
            # callback_data esperado: "bid|<player_id>|<porcentaje>"
            if data.startswith("bid|"):
                try:
                    _, player_id, pct_str = data.split("|")
                    pct = int(pct_str)
                except Exception:
                    try:
                        # Responder usando API HTTP síncrona
                        requests.post(
                            f"https://api.telegram.org/bot{token_telegram}/answerCallbackQuery",
                            json={"callback_query_id": cq.id, "text": "Datos de puja inválidos", "show_alert": True},
                            timeout=10,
                        )
                    except Exception:
                        pass
                    return jsonify({"ok": True})

                credenciales, error = login()
                if error or not credenciales.get("token"):
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{token_telegram}/answerCallbackQuery",
                            json={"callback_query_id": cq.id, "text": "No se pudo autenticar", "show_alert": True},
                            timeout=10,
                        )
                    except Exception:
                        pass
                    return jsonify({"ok": True})

                # Obtener jugadores para determinar slug, valor y si hay puja previa
                jugadores = obtener_jugadores(credenciales["token"])
                jugador = None
                try:
                    jugadores_dict = {j.get("id"): j for j in jugadores if isinstance(j, dict)}
                    jugador = jugadores_dict.get(player_id)
                except Exception:
                    jugador = None

                if not jugador:
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{token_telegram}/answerCallbackQuery",
                            json={"callback_query_id": cq.id, "text": "Jugador no encontrado", "show_alert": True},
                            timeout=10,
                        )
                    except Exception:
                        pass
                    return jsonify({"ok": True})

                base_value = int(jugador.get("value", 0) or 0)
                price = int(round(base_value * (1 + (pct / 100.0))))
                player_slug = jugador.get("slug")

                # Detectar si modificar puja existente
                try:
                    existing_bid_id = jugador.get("bid", {}).get("id") or False
                except Exception:
                    existing_bid_id = False

                # Llamar al servicio para realizar/modificar la puja
                from services.bid_service import realizar_puja
                try:
                    resultado = realizar_puja(
                        credenciales["token"],
                        player_id=player_id,
                        player_slug=player_slug,
                        price=price,
                        is_clause=False,
                        is_modify_bid=existing_bid_id,
                    )
                except Exception as e:
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{token_telegram}/answerCallbackQuery",
                            json={"callback_query_id": cq.id, "text": f"Error realizando puja: {e}", "show_alert": True},
                            timeout=10,
                        )
                    except Exception:
                        pass
                    return jsonify({"ok": True})

                # Notificar al usuario
                msg = f"Puja {'modificada' if existing_bid_id else 'realizada'}: +{pct}% por {price}"
                try:
                    # Toast del botón
                    requests.post(
                        f"https://api.telegram.org/bot{token_telegram}/answerCallbackQuery",
                        json={"callback_query_id": cq.id, "text": msg, "show_alert": False},
                        timeout=10,
                    )
                except Exception:
                    pass

                # Mensaje en el chat
                try:
                    chat_id = cq.message.chat.id if cq.message and cq.message.chat else None
                    if chat_id:
                        requests.post(
                            f"https://api.telegram.org/bot{token_telegram}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": msg,
                                "disable_web_page_preview": True,
                            },
                            timeout=10,
                        )
                except Exception:
                    pass

                try:
                    # Log simple para seguimiento
                    print(f"Puja realizada para player_id={player_id} pct={pct} price={price}")
                except Exception:
                    pass

                return jsonify({"ok": True, "result": resultado})

        # Sin callback: no hacemos nada
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200
