from flask import Flask
from config import Config
from database import db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

from routes.import_routes import import_bp  # noqa: E402
from routes.dashboard_routes import dashboard_bp  # noqa: E402
app.register_blueprint(import_bp)
app.register_blueprint(dashboard_bp)


@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JAM Report</title>
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                color: #1f2937;
            }
            .container {
                max-width: 900px;
                margin: 100px auto;
                text-align: center;
                background: white;
                padding: 50px;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }
            h1 {
                margin-bottom: 10px;
            }
            .status {
                display: inline-block;
                margin-top: 20px;
                padding: 10px 18px;
                background: #d1fae5;
                color: #065f46;
                border-radius: 20px;
                font-weight: bold;
            }
            .info {
                margin-top: 30px;
                color: #6b7280;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>JAM Report</h1>
            <div class="status">
                ✓ Aplicação funcionando
            </div>
            <div class="info">
                Python + Flask + WSGI
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/db-check")
def db_check():
    from sqlalchemy import text
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "banco": "conectado"}
    except Exception as e:
        return {"status": "erro", "detalhe": str(e)}, 500


if __name__ == "__main__":
    app.run()
