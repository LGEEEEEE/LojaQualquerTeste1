# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from app.models import User, Produto, Pedido, ItemPedido
from app import db, bcrypt
from flask_login import login_user, logout_user, login_required, current_user
import mercadopago
import os
import time

# --- NOVO ---
# Importa as classes de formulário que você criou
from app.forms import RegistrationForm, LoginForm

routes = Blueprint("routes", __name__)

# ----------------------------
# Página inicial
# ----------------------------
@routes.route("/")
def index():
    produtos = Produto.query.all()
    return render_template("index.html", produtos=produtos)

# ----------------------------
# Registro de usuário (CORRIGIDO)
# ----------------------------
@routes.route("/register", methods=["GET", "POST"])
def register():
    # Se o usuário já estiver logado, redireciona para a página inicial
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))

    # Cria uma instância do formulário de registro
    form = RegistrationForm()

    # O método validate_on_submit() verifica se é um POST e se os dados são válidos
    if form.validate_on_submit():
        # Gera o hash da senha
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        # Cria o novo usuário com os dados validados do formulário
        novo_usuario = User(username=form.username.data, email=form.email.data, password_hash=hashed_pw)

        db.session.add(novo_usuario)
        db.session.commit()

        flash("Conta criada com sucesso! Agora você pode fazer o login.", "success")
        return redirect(url_for("routes.login"))

    # Se a validação falhar ou for um GET, renderiza o template passando o formulário
    return render_template("register.html", form=form)

# ----------------------------
# Login de usuário (CORRIGIDO)
# ----------------------------
@routes.route("/login", methods=["GET", "POST"])
def login():
    # Se o usuário já estiver logado, redireciona
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))

    # Cria uma instância do formulário de login
    form = LoginForm()

    if form.validate_on_submit():
        # Busca o usuário no banco de dados pelo e-mail fornecido
        usuario = User.query.filter_by(email=form.email.data).first()
        # Verifica se o usuário existe e se a senha está correta
        if usuario and bcrypt.check_password_hash(usuario.password_hash, form.password.data):
            # Faz o login do usuário, usando a opção "Lembrar-me" do formulário
            login_user(usuario, remember=form.remember.data)
            
            # Redireciona para a página que o usuário tentava acessar antes do login
            next_page = request.args.get('next')
            flash("Login realizado com sucesso!", "success")
            return redirect(next_page) if next_page else redirect(url_for('routes.index'))
        else:
            flash("E-mail ou senha inválidos. Por favor, tente novamente.", "danger")

    return render_template("login.html", form=form)

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
# Carrinho (Mantido como estava)
# ----------------------------
@routes.route("/add_to_cart/<int:produto_id>")
@login_required # Boa prática adicionar login required para o carrinho
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
@login_required
def cart():
    cart = session.get("cart", {})
    if not cart:
        return render_template("cart.html", produtos=[], cart={})
    
    produtos = Produto.query.filter(Produto.id.in_(cart.keys())).all()
    return render_template("cart.html", produtos=produtos, cart=cart)

@routes.route("/remove_from_cart/<int:produto_id>")
@login_required
def remove_from_cart(produto_id):
    cart = session.get("cart", {})
    if str(produto_id) in cart:
        del cart[str(produto_id)]
        session.modified = True
        flash("Produto removido do carrinho.", "info")
    return redirect(url_for("routes.cart"))

# ----------------------------
# Checkout (Mantido como estava)
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
        novo_pedido = Pedido(user_id=current_user.id, total=total_final, status="Pendente")
        db.session.add(novo_pedido)
        db.session.commit()

        for produto in produtos:
            item = ItemPedido(
                pedido_id=novo_pedido.id,
                produto_id=produto.id,
                quantidade=cart[str(produto.id)],
                preco_unitario=produto.preco
            )
            db.session.add(item)
        db.session.commit()

        sdk = mercadopago.SDK(os.getenv("MERCADOPAGO_ACCESS_TOKEN"))
        base_url = os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:5000"

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
            session.pop("cart", None) # Limpa o carrinho
            return redirect(preference_response["response"]["init_point"])
        else:
            flash("Erro ao criar pagamento. Tente novamente.", "danger")
            return redirect(url_for("routes.cart"))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro durante o checkout: {e}", "danger")
        return redirect(url_for("routes.cart"))

# ----------------------------
# Webhook Mercado Pago (Mantido como estava)
# ----------------------------
@routes.route("/receber_notificacao_webhook", methods=["POST"])
def receber_notificacao_webhook():
    data = request.json
    if data and data.get("type") == "payment":
        payment_id = data.get("data", {}).get("id")
        sdk = mercadopago.SDK(os.getenv("MERCADOPAGO_ACCESS_TOKEN"))
        payment_info = sdk.payment().get(payment_id)

        if payment_info["status"] == 200:
            info = payment_info["response"]
            if info.get("status") == "approved" and info.get("external_reference"):
                try:
                    pedido_ref = info["external_reference"]
                    pedido_id = int(pedido_ref.split("-")[0])
                    pedido = Pedido.query.get(pedido_id)
                    if pedido and pedido.status != "Pago":
                        pedido.status = "Pago"
                        db.session.commit()
                except Exception as e:
                    print(f"Erro ao atualizar pedido via webhook: {e}")
    return "", 200