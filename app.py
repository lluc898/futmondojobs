
from flask import Flask
from api.jugadores import jugadores_bp
from api.bids import bids_bp

app = Flask(__name__)
app.register_blueprint(jugadores_bp)
app.register_blueprint(bids_bp)

if __name__ == "__main__":
    app.run(debug=True)