import asyncio
from flask import Blueprint, jsonify, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from services.jugadores_service import obtener_jugadores, filtrar_jugadores_positivos, obtener_informacion_userteam
from services.auth_service import login
from config import TOKEN_BOT as TOKEN, USER_ID_TELEGRAM as USER_ID

send_bp = Blueprint('send', __name__)

# Coloca tu token y tu user ID aquí
# token and user_id should be set in config or environment variables

def format_miles(value):
    """Formatea un número con separador de miles con puntos (1.000.000).
    Si no es numérico, devuelve el valor tal cual.
    """
    try:
        n = int(value)
        return f"{n:,}".replace(",", ".")
    except Exception:
        return value

def format_budget_message(userteam_info):
    """Formatea el mensaje de presupuesto con información financiera del equipo."""
    budget = userteam_info.get("budget", 0)
    max_bid = userteam_info.get("max_bid", 0)
    withheld = userteam_info.get("withheld", 0)
    balance = userteam_info.get("balance", 0)
    
    # Determinar emoji del balance
    balance_emoji = "🟢" if balance >= 0 else "🔴"
    
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Dinero disponible:</b> {format_miles(budget)}\n"
        f"🔒 <b>Pujas totales:</b> {format_miles(withheld)}\n"
        f"{balance_emoji} <b>Balance:</b> {format_miles(balance)}\n"
        f"🎯 <b>Puja máxima:</b> {format_miles(max_bid)}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

def format_player_message(player):
    nombre = player.get('nombre', 'Desconocido')
    equipo = player.get('equipo', '—')
    valor_actual = player.get('valor_actual', '—')
    cambio = player.get('cambio', 0)
    porcentaje = player.get('porcentaje', 0)

    # Formatear valores numéricos con puntos para miles
    valor_actual_fmt = format_miles(valor_actual)
    cambio_fmt = format_miles(abs(cambio))  # Valor absoluto para el formato

    try:
        porcentaje_text = f"{porcentaje:.2f}%"
    except Exception:
        porcentaje_text = f"{porcentaje}%"
    
    # Determinar emoji y signo según si es positivo, negativo o neutro
    if cambio > 0:
        emoji = "🔥"
        titulo = "Jugador en tendencia"
        signo = "+"
    elif cambio < 0:
        emoji = "📉"
        titulo = "Jugador bajando"
        signo = "-"
    else:
        emoji = "➖"
        titulo = "Jugador estable"
        signo = ""

    return (
        f"{emoji} <b>{titulo}</b>\n"
        f"👤 <b>{nombre}</b>\n"
        f"🏟️ <i>{equipo}</i>\n"
        f"💰 Valor actual: <b>{valor_actual_fmt}</b>\n"
        f"📈 Cambio: <b>{signo}{cambio_fmt}</b> (<b>{signo}{porcentaje_text}</b>)"
    )

async def send_message():
    token_telegram = TOKEN
    bot = Bot(token=token_telegram)
    credenciales, error = login()
    if error or not credenciales["token"]:
        print("No se pudo autenticar")
        return
    
    # Obtener información del userteam y enviar mensaje de buenos días
    try:
        userteam_info = obtener_informacion_userteam(credenciales["token"])
        budget_message = format_budget_message(userteam_info)
        await bot.send_message(
            chat_id=USER_ID,
            text=budget_message,
            parse_mode="HTML",
        )
        await asyncio.sleep(0.5)
    except Exception as e:
        print(f"Error obteniendo/enviando información de presupuesto: {e}")
    
    # Obtener jugadores disponibles
    available_players = obtener_jugadores(credenciales["token"])
    # Ordenar todos los jugadores por cambio de valor (mayor a menor)
    all_players = filtrar_jugadores_positivos(available_players)

    if not all_players:
        user_telegram = USER_ID
        await bot.send_message(
            chat_id=user_telegram,
            text="😴 No hay jugadores disponibles en este momento.",
            parse_mode="HTML",
        )
        return

    # Enviar cada jugador en un mensaje separado
    for player in all_players:
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

                # Notificar al usuario (mensaje vistoso y más destacado)
                formatted_price = format_miles(price)
                accion = 'modificada' if existing_bid_id else 'realizada'
                emoji_accion = '♻️' if existing_bid_id else '✅'
                nombre_jugador = (
                    (jugador.get('name') or jugador.get('nombre')) if isinstance(jugador, dict) else None
                ) or 'Jugador'
                equipo_jugador = (
                    (jugador.get('team') or jugador.get('equipo')) if isinstance(jugador, dict) else None
                ) or ''

                # Toast breve para el botón (sin HTML)
                msg = f"Puja {accion}: +{pct}% por {formatted_price}"

                # Mensaje enriquecido para el chat con HTML
                msg_html = (
                    f"{emoji_accion} <b>Puja {accion.upper()}</b> {emoji_accion}\n"
                    f"👤 <b>{nombre_jugador}</b>"
                    + (f" — <i>{equipo_jugador}</i>\n" if equipo_jugador else "\n")
                    + f"📈 Incremento: <b>+{pct}%</b>\n"
                    + f"💶 Importe: <b>{formatted_price}</b>"
                )
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
                                "text": msg_html,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True,
                            },
                            timeout=10,
                        )
                        
                        # Enviar información actualizada del presupuesto después de la puja
                        try:
                            userteam_info = obtener_informacion_userteam(credenciales["token"])
                            budget_message = format_budget_message(userteam_info)
                            requests.post(
                                f"https://api.telegram.org/bot{token_telegram}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": budget_message,
                                    "parse_mode": "HTML",
                                },
                                timeout=10,
                            )
                        except Exception as e_budget:
                            print(f"Error enviando presupuesto actualizado: {e_budget}")
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
