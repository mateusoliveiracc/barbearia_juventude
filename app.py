"""
Barbearia Juventude - Sistema de Agendamento
Aplicação Flask + SQLite (biblioteca padrão do Python, sem ORM externo)
para gerenciar agendamentos de clientes e um painel administrativo
protegido por login.

Para rodar (no PyCharm ou terminal):
    pip install -r requirements.txt
    python app.py
Depois acesse http://127.0.0.1:5000
"""

import os
import sqlite3
from datetime import datetime, timedelta, date as date_cls
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, "barbearia.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-essa-chave-em-producao")


# ----------------------------------------------------------------------------
# CONFIGURAÇÃO DA BARBEARIA (fácil de editar)
# ----------------------------------------------------------------------------

HORARIO_FUNCIONAMENTO = {
    # 0 = segunda ... 6 = domingo
    0: ("09:00", "20:00"),
    1: ("09:00", "20:00"),
    2: ("09:00", "20:00"),
    3: ("09:00", "20:00"),
    4: ("08:00", "20:00"),
    5: ("08:00", "18:00"),
    6: None,  # domingo fechado
}

DIAS_SEMANA_PT = ["Segunda-feira", "Terça-feira", "Quarta-feira",
                   "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

INTERVALO_SLOT_MIN = 30  # granularidade dos horários exibidos

EMPRESA = {
    "nome": "Barbearia Juventude",
    "nota": "5.0",
    "endereco": "Avenida Antônio de Pinho Tavares, 136 - Conjunto Cristina (São Benedito), Santa Luzia/MG - CEP 33105-500",
    "telefone": "(31) 98268-6431",
    "telefone_link": "5531982686431",
    "instagram": "https://www.instagram.com/barbearia_juventude/",
    "comodidades": ["Wi-fi", "Estacionamento", "Acessibilidade", "Atende crianças"],
    "pagamentos": ["Dinheiro", "Cartão de Crédito", "Cartão de Débito"],
}

ADMIN_USER_PADRAO = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS_PADRAO = os.environ.get("ADMIN_PASS", "barbearia123")

SERVICOS_INICIAIS = [
    ("Corte", "R$ 35,00", 40),
    ("Barba", "Consultar", 20),
    ("Corte e Barba", "A partir de R$ 60,00", 60),
    ("Acabamento", "R$ 18,00", 20),
    ("Corte e Sobrancelhas", "R$ 40,00", 40),
    ("Corte Barba e Sobrancelhas", "Consultar", 60),
    ("Corte e Botox", "R$ 120,00", 60),
    ("Corte e Luzes", "R$ 90,00", 60),
    ("Corte e Tintura", "R$ 70,00", 60),
    ("Corte Infantil", "R$ 35,00", 40),
    ("Botox Capilar", "Consultar", 40),
    ("Cabelo Platinado", "Consultar", 60),
    ("Luzes", "Consultar", 40),
    ("Pigmentação", "A partir de R$ 30,00", 20),
    ("Progressiva Masculina", "Consultar", 40),
    ("Relaxamento", "A partir de R$ 35,00", 20),
    ("Sobrancelhas", "Consultar", 20),
]

BARBEIROS_INICIAIS = [
    "Haylander Heiderich",
]


# ----------------------------------------------------------------------------
# BANCO DE DADOS (sqlite3 puro)
# ----------------------------------------------------------------------------

def get_db():
    """Retorna a conexão SQLite da requisição atual (criada uma vez por request)."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def fechar_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def criar_tabelas():
    """Cria as tabelas do banco caso não existam."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS servico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco_texto TEXT NOT NULL,
            duracao_min INTEGER NOT NULL DEFAULT 30,
            ativo INTEGER NOT NULL DEFAULT 1,
            ordem INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS barbeiro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            ordem INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT NOT NULL,
            cliente_telefone TEXT NOT NULL,
            servico_id INTEGER NOT NULL,
            barbeiro_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            observacoes TEXT,
            status TEXT NOT NULL DEFAULT 'confirmado',
            criado_em TEXT NOT NULL,
            FOREIGN KEY (servico_id) REFERENCES servico (id),
            FOREIGN KEY (barbeiro_id) REFERENCES barbeiro (id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def migrar_banco_existente():
    """Garante compatibilidade com bancos criados antes da função de barbeiros.
    Adiciona a coluna barbeiro_id em agendamento caso ainda não exista, e
    associa agendamentos antigos ao primeiro barbeiro cadastrado."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    colunas = [linha[1] for linha in cur.execute("PRAGMA table_info(agendamento)").fetchall()]
    if "barbeiro_id" not in colunas:
        cur.execute("ALTER TABLE agendamento ADD COLUMN barbeiro_id INTEGER")

        cur.execute("SELECT COUNT(*) FROM barbeiro")
        if cur.fetchone()[0] == 0:
            for i, nome in enumerate(BARBEIROS_INICIAIS):
                cur.execute(
                    "INSERT INTO barbeiro (nome, ativo, ordem) VALUES (?, 1, ?)",
                    (nome, i),
                )

        primeiro_barbeiro = cur.execute(
            "SELECT id FROM barbeiro ORDER BY ordem LIMIT 1"
        ).fetchone()
        if primeiro_barbeiro:
            cur.execute(
                "UPDATE agendamento SET barbeiro_id = ? WHERE barbeiro_id IS NULL",
                (primeiro_barbeiro[0],),
            )
        conn.commit()
        print("Banco migrado: coluna barbeiro_id adicionada aos agendamentos.")

    conn.close()


def popular_dados_iniciais():
    """Insere serviços e admin padrão se o banco estiver vazio."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM servico")
    if cur.fetchone()[0] == 0:
        for i, (nome, preco, dur) in enumerate(SERVICOS_INICIAIS):
            cur.execute(
                "INSERT INTO servico (nome, preco_texto, duracao_min, ativo, ordem) VALUES (?, ?, ?, 1, ?)",
                (nome, preco, dur, i),
            )
        conn.commit()
        print("Servicos iniciais cadastrados.")

    cur.execute("SELECT COUNT(*) FROM barbeiro")
    if cur.fetchone()[0] == 0:
        for i, nome in enumerate(BARBEIROS_INICIAIS):
            cur.execute(
                "INSERT INTO barbeiro (nome, ativo, ordem) VALUES (?, 1, ?)",
                (nome, i),
            )
        conn.commit()
        print("Barbeiros iniciais cadastrados.")

    cur.execute("SELECT COUNT(*) FROM admin")
    if cur.fetchone()[0] == 0:
        senha_hash = generate_password_hash(ADMIN_PASS_PADRAO)
        cur.execute(
            "INSERT INTO admin (usuario, senha_hash) VALUES (?, ?)",
            (ADMIN_USER_PADRAO, senha_hash),
        )
        conn.commit()
        print(f"Admin criado -> usuario: {ADMIN_USER_PADRAO} | senha: {ADMIN_PASS_PADRAO}")
        print("   (recomendado: troque a senha depois de logar pela primeira vez)")

    conn.close()


# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)
    return wrapped


def _hhmm_para_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def gerar_slots_do_dia(dia: date_cls):
    """Gera lista de horários possíveis (strings HH:MM) para um dia, respeitando
    o horário de funcionamento. Não filtra ocupados aqui."""
    config = HORARIO_FUNCIONAMENTO.get(dia.weekday())
    if not config:
        return []
    abertura, fechamento = config
    h_ini = datetime.strptime(abertura, "%H:%M")
    h_fim = datetime.strptime(fechamento, "%H:%M")

    slots = []
    atual = h_ini
    while atual < h_fim:
        slots.append(atual.strftime("%H:%M"))
        atual += timedelta(minutes=INTERVALO_SLOT_MIN)
    return slots


def slot_cabe_no_horario(hora_str: str, duracao_min: int, dia: date_cls):
    """Confere se um serviço de X minutos, iniciando em hora_str, termina
    antes do fechamento daquele dia."""
    config = HORARIO_FUNCIONAMENTO.get(dia.weekday())
    if not config:
        return False
    _, fechamento = config
    inicio = datetime.strptime(hora_str, "%H:%M")
    fim_servico = inicio + timedelta(minutes=duracao_min)
    fim_expediente = datetime.strptime(fechamento, "%H:%M")
    return fim_servico <= fim_expediente


def horarios_disponiveis(dia: date_cls, barbeiro_id: int, duracao_min: int):
    """Retorna os horários livres de um barbeiro específico em um dia,
    considerando a duração do serviço escolhido e os agendamentos já
    existentes daquele barbeiro que se sobreponham."""
    todos_slots = gerar_slots_do_dia(dia)
    if not todos_slots:
        return []

    db = get_db()
    linhas = db.execute(
        """
        SELECT a.hora, s.duracao_min
        FROM agendamento a
        JOIN servico s ON s.id = a.servico_id
        WHERE a.data = ? AND a.barbeiro_id = ? AND a.status = 'confirmado'
        """,
        (dia.isoformat(), barbeiro_id),
    ).fetchall()

    ocupados = []
    for linha in linhas:
        ini_min = _hhmm_para_min(linha["hora"])
        dur = linha["duracao_min"] or 30
        ocupados.append((ini_min, ini_min + dur))

    agora = datetime.now()
    is_hoje = dia == agora.date()

    disponiveis = []
    for slot in todos_slots:
        if not slot_cabe_no_horario(slot, duracao_min, dia):
            continue

        slot_min = _hhmm_para_min(slot)

        if is_hoje and slot_min <= agora.hour * 60 + agora.minute:
            continue

        slot_fim = slot_min + duracao_min
        conflita = any(slot_min < fim and slot_fim > ini for ini, fim in ocupados)
        if not conflita:
            disponiveis.append(slot)

    return disponiveis


def buscar_servico(servico_id):
    db = get_db()
    return db.execute("SELECT * FROM servico WHERE id = ?", (servico_id,)).fetchone()


def buscar_barbeiro(barbeiro_id):
    db = get_db()
    return db.execute("SELECT * FROM barbeiro WHERE id = ?", (barbeiro_id,)).fetchone()


# ----------------------------------------------------------------------------
# ROTAS PÚBLICAS
# ----------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    servicos = db.execute(
        "SELECT * FROM servico WHERE ativo = 1 ORDER BY ordem, nome"
    ).fetchall()
    return render_template(
        "index.html",
        empresa=EMPRESA,
        servicos=servicos,
        horario=HORARIO_FUNCIONAMENTO,
        dias_semana=DIAS_SEMANA_PT,
    )


@app.route("/agendar", methods=["GET", "POST"])
def agendar():
    db = get_db()
    servicos = db.execute(
        "SELECT * FROM servico WHERE ativo = 1 ORDER BY ordem, nome"
    ).fetchall()
    barbeiros = db.execute(
        "SELECT * FROM barbeiro WHERE ativo = 1 ORDER BY ordem, nome"
    ).fetchall()
    servico_id_pre = request.args.get("servico_id", type=int)

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        servico_id = request.form.get("servico_id", type=int)
        barbeiro_id = request.form.get("barbeiro_id", type=int)
        data_str = request.form.get("data", "")
        hora = request.form.get("hora", "")
        observacoes = request.form.get("observacoes", "").strip()

        erro = None
        servico = buscar_servico(servico_id) if servico_id else None
        barbeiro = buscar_barbeiro(barbeiro_id) if barbeiro_id else None
        dia = None

        if not nome or not telefone or not servico or not barbeiro or not data_str or not hora:
            erro = "Por favor, preencha todos os campos obrigatórios."
        else:
            try:
                dia = datetime.strptime(data_str, "%Y-%m-%d").date()
            except ValueError:
                erro = "Data inválida."

            if not erro:
                if dia < date_cls.today():
                    erro = "Não é possível agendar em uma data passada."
                elif hora not in horarios_disponiveis(dia, barbeiro["id"], servico["duracao_min"]):
                    erro = "Esse horário não está mais disponível. Escolha outro."

        if erro:
            flash(erro, "error")
            return render_template(
                "agendar.html", empresa=EMPRESA, servicos=servicos, barbeiros=barbeiros,
                servico_id_pre=servico_id, form=request.form
            )

        cur = db.execute(
            """
            INSERT INTO agendamento
                (cliente_nome, cliente_telefone, servico_id, barbeiro_id, data, hora, observacoes, status, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmado', ?)
            """,
            (nome, telefone, servico["id"], barbeiro["id"], dia.isoformat(), hora, observacoes,
             datetime.now().isoformat()),
        )
        db.commit()
        novo_id = cur.lastrowid

        return redirect(url_for("agendamento_confirmado", agendamento_id=novo_id))

    return render_template(
        "agendar.html", empresa=EMPRESA, servicos=servicos, barbeiros=barbeiros,
        servico_id_pre=servico_id_pre, form={}
    )


@app.route("/agendamento/<int:agendamento_id>/confirmado")
def agendamento_confirmado(agendamento_id):
    db = get_db()
    ag = db.execute(
        """
        SELECT a.*, s.nome AS servico_nome, b.nome AS barbeiro_nome
        FROM agendamento a
        JOIN servico s ON s.id = a.servico_id
        JOIN barbeiro b ON b.id = a.barbeiro_id
        WHERE a.id = ?
        """,
        (agendamento_id,),
    ).fetchone()
    if ag is None:
        flash("Agendamento não encontrado.", "error")
        return redirect(url_for("index"))

    data_formatada = datetime.strptime(ag["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
    return render_template("confirmado.html", empresa=EMPRESA, ag=ag, data_formatada=data_formatada)


@app.route("/api/horarios")
def api_horarios():
    """Retorna horários disponíveis em JSON para um barbeiro, serviço e data via AJAX."""
    data_str = request.args.get("data")
    servico_id = request.args.get("servico_id", type=int)
    barbeiro_id = request.args.get("barbeiro_id", type=int)

    if not data_str or not servico_id or not barbeiro_id:
        return jsonify({"erro": "parâmetros faltando"}), 400

    try:
        dia = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"erro": "data inválida"}), 400

    servico = buscar_servico(servico_id)
    barbeiro = buscar_barbeiro(barbeiro_id)
    if not servico or not barbeiro:
        return jsonify({"erro": "serviço ou barbeiro não encontrado"}), 404

    if dia < date_cls.today():
        return jsonify({"horarios": []})

    slots = horarios_disponiveis(dia, barbeiro["id"], servico["duracao_min"])
    return jsonify({"horarios": slots})


# ----------------------------------------------------------------------------
# ROTAS ADMIN
# ----------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        db = get_db()
        admin = db.execute(
            "SELECT * FROM admin WHERE usuario = ?",
            (usuario,)
        ).fetchone()

        if admin and check_password_hash(admin["senha_hash"], senha):
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin_dashboard"))

        flash("Usuário ou senha inválidos", "error")

    return render_template("admin_login.html", empresa=EMPRESA)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()

    data_str = request.args.get("data")
    if data_str:
        try:
            dia_filtro = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            dia_filtro = date_cls.today()
    else:
        dia_filtro = date_cls.today()

    barbeiro_filtro_id = request.args.get("barbeiro_id", type=int)

    query = """
        SELECT a.*, s.nome AS servico_nome, b.nome AS barbeiro_nome
        FROM agendamento a
        JOIN servico s ON s.id = a.servico_id
        JOIN barbeiro b ON b.id = a.barbeiro_id
        WHERE a.data = ?
    """
    params = [dia_filtro.isoformat()]

    if barbeiro_filtro_id:
        query += " AND a.barbeiro_id = ?"
        params.append(barbeiro_filtro_id)

    query += " ORDER BY a.hora"

    agendamentos = db.execute(query, params).fetchall()

    total_hoje = len(agendamentos)
    confirmados = len([a for a in agendamentos if a["status"] == "confirmado"])

    proximos = db.execute(
        """
        SELECT a.*, s.nome AS servico_nome, b.nome AS barbeiro_nome
        FROM agendamento a
        JOIN servico s ON s.id = a.servico_id
        JOIN barbeiro b ON b.id = a.barbeiro_id
        WHERE a.data >= ? AND a.status = 'confirmado'
        ORDER BY a.data, a.hora
        LIMIT 5
        """,
        (date_cls.today().isoformat(),),
    ).fetchall()

    # pré-formata datas para exibição (evita lógica de data no Jinja)
    proximos_fmt = []
    for p in proximos:
        d = dict(p)
        d["data_fmt"] = datetime.strptime(p["data"], "%Y-%m-%d").strftime("%d/%m")
        proximos_fmt.append(d)

    barbeiros = db.execute("SELECT * FROM barbeiro ORDER BY ordem, nome").fetchall()

    return render_template(
        "admin_dashboard.html",
        empresa=EMPRESA,
        agendamentos=agendamentos,
        dia_filtro=dia_filtro,
        total_hoje=total_hoje,
        confirmados=confirmados,
        proximos=proximos_fmt,
        barbeiros=barbeiros,
        barbeiro_filtro_id=barbeiro_filtro_id,
    )


@app.route("/admin/agendamento/<int:agendamento_id>/cancelar", methods=["POST"])
@login_required
def admin_cancelar(agendamento_id):
    db = get_db()
    db.execute("UPDATE agendamento SET status = 'cancelado' WHERE id = ?", (agendamento_id,))
    db.commit()
    flash("Agendamento cancelado.", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/agendamento/<int:agendamento_id>/reativar", methods=["POST"])
@login_required
def admin_reativar(agendamento_id):
    db = get_db()
    db.execute("UPDATE agendamento SET status = 'confirmado' WHERE id = ?", (agendamento_id,))
    db.commit()
    flash("Agendamento reativado.", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/agendamento/<int:agendamento_id>/excluir", methods=["POST"])
@login_required
def admin_excluir(agendamento_id):
    db = get_db()
    db.execute("DELETE FROM agendamento WHERE id = ?", (agendamento_id,))
    db.commit()
    flash("Agendamento excluído.", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/servicos")
@login_required
def admin_servicos():
    db = get_db()
    servicos = db.execute("SELECT * FROM servico ORDER BY ordem, nome").fetchall()
    return render_template("admin_servicos.html", empresa=EMPRESA, servicos=servicos)


@app.route("/admin/servicos/<int:servico_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_servico(servico_id):
    db = get_db()
    db.execute("UPDATE servico SET ativo = 1 - ativo WHERE id = ?", (servico_id,))
    db.commit()
    return redirect(url_for("admin_servicos"))


@app.route("/admin/servicos/novo", methods=["GET", "POST"])
@login_required
def admin_novo_servico():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        preco_texto = request.form.get("preco_texto", "").strip()
        duracao_min = request.form.get("duracao_min", type=int) or 30

        if nome and preco_texto:
            db = get_db()
            maior_ordem = db.execute("SELECT MAX(ordem) FROM servico").fetchone()[0] or 0
            db.execute(
                "INSERT INTO servico (nome, preco_texto, duracao_min, ativo, ordem) VALUES (?, ?, ?, 1, ?)",
                (nome, preco_texto, duracao_min, maior_ordem + 1),
            )
            db.commit()
            flash("Serviço adicionado.", "success")
            return redirect(url_for("admin_servicos"))
        flash("Preencha nome e preço.", "error")

    return render_template("admin_novo_servico.html", empresa=EMPRESA)


@app.route("/admin/servicos/<int:servico_id>/excluir", methods=["POST"])
@login_required
def admin_excluir_servico(servico_id):
    db = get_db()
    tem_agendamentos = db.execute(
        "SELECT 1 FROM agendamento WHERE servico_id = ? LIMIT 1", (servico_id,)
    ).fetchone()

    if tem_agendamentos:
        flash("Não é possível excluir: existem agendamentos vinculados a esse serviço. Desative-o em vez disso.", "error")
    else:
        db.execute("DELETE FROM servico WHERE id = ?", (servico_id,))
        db.commit()
        flash("Serviço excluído.", "success")
    return redirect(url_for("admin_servicos"))


@app.route("/admin/barbeiros")
@login_required
def admin_barbeiros():
    db = get_db()
    barbeiros = db.execute("SELECT * FROM barbeiro ORDER BY ordem, nome").fetchall()
    return render_template("admin_barbeiros.html", empresa=EMPRESA, barbeiros=barbeiros)


@app.route("/admin/barbeiros/<int:barbeiro_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_barbeiro(barbeiro_id):
    db = get_db()
    db.execute("UPDATE barbeiro SET ativo = 1 - ativo WHERE id = ?", (barbeiro_id,))
    db.commit()
    return redirect(url_for("admin_barbeiros"))


@app.route("/admin/barbeiros/novo", methods=["GET", "POST"])
@login_required
def admin_novo_barbeiro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()

        if nome:
            db = get_db()
            maior_ordem = db.execute("SELECT MAX(ordem) FROM barbeiro").fetchone()[0] or 0
            db.execute(
                "INSERT INTO barbeiro (nome, ativo, ordem) VALUES (?, 1, ?)",
                (nome, maior_ordem + 1),
            )
            db.commit()
            flash("Barbeiro adicionado.", "success")
            return redirect(url_for("admin_barbeiros"))
        flash("Preencha o nome do barbeiro.", "error")

    return render_template("admin_novo_barbeiro.html", empresa=EMPRESA)


@app.route("/admin/barbeiros/<int:barbeiro_id>/excluir", methods=["POST"])
@login_required
def admin_excluir_barbeiro(barbeiro_id):
    db = get_db()
    tem_agendamentos = db.execute(
        "SELECT 1 FROM agendamento WHERE barbeiro_id = ? LIMIT 1", (barbeiro_id,)
    ).fetchone()

    if tem_agendamentos:
        flash("Não é possível excluir: existem agendamentos vinculados a esse barbeiro. Desative-o em vez disso.", "error")
    else:
        db.execute("DELETE FROM barbeiro WHERE id = ?", (barbeiro_id,))
        db.commit()
        flash("Barbeiro excluído.", "success")
    return redirect(url_for("admin_barbeiros"))


# ----------------------------------------------------------------------------
# INICIALIZAÇÃO DO BANCO (executa ao importar o módulo)
# ----------------------------------------------------------------------------

criar_tabelas()
migrar_banco_existente()
popular_dados_iniciais()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
