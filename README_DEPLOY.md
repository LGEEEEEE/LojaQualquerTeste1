# Deploy da Loja (Flask + Gunicorn)

Este projeto é um app Flask pronto para deploy com **Gunicorn**.

## Requisitos
- Python 3.11+ (recomendado 3.12)
- Variáveis de ambiente configuradas na plataforma de deploy (NÃO subir o arquivo `.env` público)

### Variáveis necessárias
- `MP_ACCESS_TOKEN` — Token de acesso da API do Mercado Pago
- `MP_PUBLIC_KEY` — Public Key (Front-end)
- `FLASK_SECRET_KEY` — chave secreta para sessões
- `DATABASE_URL` (opcional) — se for usar um banco gerenciado (ex.: Postgres). Se ausente, o app usa SQLite local (não recomendado em produção).

## Como rodar localmente
```bash
python -m venv .venv
source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=run.py  # Windows: set FLASK_APP=run.py
flask run
```

## Entrypoint de Produção
O Procfile já está configurado para:
```
web: gunicorn run:app
```

## Deploy no Render (passo a passo)
1. Crie um repositório no GitHub e suba os arquivos (NÃO suba `.env`).
2. No **Render**, crie um novo **Web Service** via "Build & deploy from a Git repository".
3. Selecione o repositório. Configure:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
4. Em **Environment**, adicione as variáveis:
   - `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `FLASK_SECRET_KEY`
5. (Opcional) Ajuste **Disk** se precisar de persistência. Em produção, prefira Postgres gerenciado.
6. Deploy.

## Deploy no Railway (passo a passo)
1. Conecte o repositório no **Railway**.
2. Em **Variables**, adicione `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `FLASK_SECRET_KEY`.
3. Em **Start Command** coloque: `gunicorn run:app`
4. Railway detecta Python automaticamente e executa `pip install -r requirements.txt`.
5. Deploy.

## Webhooks / Notificações do Mercado Pago
- Atualize qualquer URL hardcoded que aponte para `ngrok` para a URL pública do serviço (ex.: `https://seuapp.onrender.com/webhook`).
- Revise as rotas em `app/routes.py` para garantir que a **notificação de pagamento** está exposta publicamente e sem `debug=True`.

## Segurança
- Nunca comite o `.env` com chaves reais.
- Ative HTTPS/SSL (a maioria das plataformas já fornece).
- Desative `debug=True` em produção (o Gunicorn não usa isso).

## Observações
- O projeto usa templates Jinja2 em `app/templates` e assets em `app/static`.
- Se precisar mudar o banco para Postgres, ajuste a URL no `app/__init__.py` para ler `DATABASE_URL`.
