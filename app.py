from flask import Flask
from api.jugadores import jugadores_bp
from telegram_bot.send import send_bp

app = Flask(__name__)
app.register_blueprint(jugadores_bp)
app.register_blueprint(send_bp)

if __name__ == "__main__":
    app.run(debug=True)