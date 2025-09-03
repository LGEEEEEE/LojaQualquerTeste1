# Lê a URL do banco de dados do ambiente
database_url = os.getenv("DATABASE_URL")

# Se a URL existir e for de um banco Postgres, ajusta para usar o driver 'psycopg'
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

# Define a configuração final. Se a URL não existir, usa o SQLite local.
SQLALCHEMY_DATABASE_URI = database_url or "sqlite:///database.db"