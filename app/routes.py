# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from app.models import Usuario, Produto, Pedido, ItemPedido
from app import db, bcrypt
from flask_login import login_user, logout_user, login_required, current_user
import mercadopago
import os
import time

routes = Blueprint("routes", __name__)

# ----------------------------
# Página inicial
# ----------------------------
@routes.route("/")
def index():
    produtos = Produto.query.all()
    return render_template("index.html", produtos=produtos)

# ----------------------------
# Registro de usuário
# ----------------------------
@routes.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash("E-mail já cadastrado", "danger")
            return redirect(url_for("routes.register"))

        hashed_pw = bcrypt.generate_password_hash(senha).decode("utf-8")
        novo_usuario = Usuario(nome=nome, email=email, senha=hashed_pw)

        db.session.add(novo_usuario)
        db.session.commit()

        flash("Conta criada com sucesso!", "success")
        return redirect(url_for("routes.login"))

    return render_template("register.html")

# ----------------------------
# Login de usuário
# ----------------------------
@routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and bcrypt.check_password_hash(usuario.senha, senha):
            login_user(usuario)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("routes.index"))
        else:
            flash("E-mail ou senha inválidos", "danger")

    return render_template("login.html")

# ----------------------------
# Logout
# ----------------------------
@routes.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("routes.index"))

# ----------------------------
# Carrinho
# ----------------------------
@routes.route("/add_to_cart/<int:produto_id>")
def add_to_cart(produto_id):
    produto = Produto.query.get_or_404(produto_id)

    if "cart" not in session:
        session["cart"] = {}

    cart = session["cart"]
    cart[str(produto_id)] = cart.get(str(produto_id), 0) + 1
    session.modified = True

    flash(f"{produto.nome} adicionado ao carrinho!", "success")
    return redirect(url_for("routes.index"))

@routes.route("/cart")
def cart():
    cart = session.get("cart", {})
    produtos = Produto.query.filter(Produto.id.in_(cart.keys())).all()
    return render_template("cart.html", produtos=produtos, cart=cart)

@routes.route("/remove_from_cart/<int:produto_id>")
def remove_from_cart(produto_id):
    cart = session.get("cart", {})
    if str(produto_id) in cart:
        del cart[str(produto_id)]
        session.modified = True
        flash("Produto removido do carrinho.", "info")
    return redirect(url_for("routes.cart"))

# ----------------------------
# Checkout
# ----------------------------
@routes.route("/checkout")
@login_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Seu carrinho está vazio.", "warning")
        return redirect(url_for("routes.index"))

    produtos = Produto.query.filter(Produto.id.in_(cart.keys())).all()
    total_final = sum(produto.preco * cart[str(produto.id)] for produto in produtos)

    try:
        # Criar o pedido no banco
        novo_pedido = Pedido(usuario_id=current_user.id, total=total_final, status="Pendente")
        db.session.add(novo_pedido)
        db.session.commit()

        # Adicionar os itens
        for produto in produtos:
            item = ItemPedido(
                pedido_id=novo_pedido.id,
                produto_id=produto.id,
                quantidade=cart[str(produto.id)],
                preco_unitario=produto.preco
            )
            db.session.add(item)
        db.session.commit()

        # Mercado Pago
        sdk = mercadopago.SDK(os.getenv("MERCADOPAGO_ACCESS_TOKEN"))

        # URL base dinâmica
        base_url = (
            os.getenv("BASE_URL")
            or os.getenv("RENDER_EXTERNAL_URL")
            or os.getenv("RAILWAY_PUBLIC_DOMAIN")
            or "http://127.0.0.1:5000"
        )

        # Criar preferência de pagamento
        preference_data = {
            "items": [
                {
                    "title": "Compra na Loja",
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": float(total_final),
                }
            ],
            "back_urls": {
                "success": f"{base_url}/success",
                "failure": f"{base_url}/failure",
                "pending": f"{base_url}/pending",
            },
            "auto_return": "approved",
            "notification_url": f"{base_url}/receber_notificacao_webhook",
            "external_reference": f"{novo_pedido.id}-{int(time.time())}",
        }

        preference_response = sdk.preference().create(preference_data)

        if preference_response["status"] == 201:
            session["cart"] = {}
            return redirect(preference_response["response"]["init_point"])
        else:
            flash("Erro ao criar pagamento. Tente novamente.", "danger")
            return redirect(url_for("routes.cart"))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro durante o checkout: {e}", "danger")
        return redirect(url_for("routes.cart"))

# ----------------------------
# Webhook Mercado Pago
# ----------------------------
@routes.route("/receber_notificacao_webhook", methods=["POST"])
def receber_notificacao_webhook():
    data = request.json
    print("Webhook recebido:", data)

    if data.get("type") == "payment":
        payment_id = data.get("data", {}).get("id")
        sdk = mercadopago.SDK(os.getenv("MERCADOPAGO_ACCESS_TOKEN"))
        payment_info = sdk.payment().get(payment_id)

        if payment_info["status"] == 200:
            info = payment_info["response"]
            if info.get("status") == "approved" and info.get("external_reference"):
                try:
                    # Corrigido: pega só o ID antes do "-"
                    pedido_ref = info["external_reference"]
                    pedido_id = int(pedido_ref.split("-")[0])

                    pedido = Pedido.query.get(pedido_id)
                    if pedido:
                        pedido.status = "Pago"
                        db.session.commit()
                        print(f"Pedido {pedido_id} atualizado para Pago")
                except Exception as e:
                    print(f"Erro ao atualizar pedido: {e}")

    return "", 200
