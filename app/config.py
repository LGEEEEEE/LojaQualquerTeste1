import os

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "default_key")
    # Remova a parte .replace() da linha abaixo
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False