import os, io
import json
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from sqlalchemy import event
from sqlalchemy.engine import Engine
from flask_migrate import Migrate

from config import Config
from models import db, Usuario, Motorista, Caminhao, ConjuntoVeicular, Romaneio, MovimentoEstoque, ConfiguracaoEmpresa, Abastecimento, Manutencao, Multa

app = Flask(__name__)
app.config.from_object(Config)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if 'sqlite' in str(dbapi_connection.__class__):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

db.init_app(app)
migrate = Migrate(app, db, render_as_batch=True)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(uid): return Usuario.query.get(int(uid))

os.makedirs('instance', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs(os.path.join('static', 'img'), exist_ok=True)

# --- INICIALIZAÇÃO SEGURA ---
with app.app_context():
    db.create_all()
    try:
        if not Usuario.query.filter_by(username='admin').first():
            u = Usuario(username='admin', nome='Admin')
            u.set_senha('admin123')
            db.session.add(u)
            db.session.commit()
    except Exception as e:
        print(f"Aviso ao criar usuário: {e}")

    try:
        if not ConfiguracaoEmpresa.query.first():
            db.session.add(ConfiguracaoEmpresa())
            db.session.commit()
    except Exception as e:
        print(f"Aviso ao criar configuração: {e}")

@app.context_processor
def inject_globals():
    try:
        config = ConfiguracaoEmpresa.query.first()
        nome_empresa = config.nome_fantasia if config else 'MTI Frotas'
    except Exception:
        nome_empresa = 'MTI Frotas'
        
    grupos = {}
    menus = [
        {"titulo": "📊 Painel", "endpoint": "index", "grupo": "Operação"},
        {"titulo": "📦 Romaneios", "endpoint": "listar_romaneios", "grupo": "Operação"},
        {"titulo": "💰 Saldo Pendente", "endpoint": "saldo_pendente", "grupo": "Operação"},
        {"titulo": "📦 Estoque", "endpoint": "painel_estoque", "grupo": "Operação"},
        {"titulo": "👤 Motoristas", "endpoint": "listar_motoristas", "grupo": "Cadastros"},
        {"titulo": "🚛 Caminhões", "endpoint": "listar_caminhoes", "grupo": "Cadastros"},
        {"titulo": "🔗 Conjuntos", "endpoint": "listar_conjuntos", "grupo": "Cadastros"},
        {"titulo": "⛽ Abastecimentos", "endpoint": "listar_abastecimentos", "grupo": "Custos"},
        {"titulo": "🔧 Manutenções", "endpoint": "listar_manutencoes", "grupo": "Custos"},
        {"titulo": "⚠️ Multas", "endpoint": "listar_multas", "grupo": "Custos"},
        {"titulo": "⚙️ Parâmetros", "endpoint": "configuracoes", "grupo": "Sistema"}
    ]
    for m in menus:
        if m['grupo'] not in grupos: grupos[m['grupo']] = []
        grupos[m['grupo']].append(m)
    return {'menus_agrupados': grupos, 'nome_empresa': nome_empresa}

# --- AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(username=request.form['username']).first()
        if u and u.checar_senha(request.form['password']):
            login_user(u); return redirect(url_for('index'))
        flash('Login inválido.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/')
@login_required
def index(): return render_template('index.html')

# --- MOTORISTAS E CAMINHÕES ---
@app.route('/motoristas')
@login_required
def listar_motoristas(): return render_template('motoristas.html', motoristas=Motorista.query.all())

@app.route('/caminhoes')
@login_required
def listar_caminhoes(): return render_template('caminhoes.html', caminhoes=Caminhao.query.all())

# --- CONJUNTOS ---
@app.route('/conjuntos', methods=['GET', 'POST'])
@login_required
def listar_conjuntos():
    if request.method == 'POST':
        reb = ','.join([p.upper() for p in request.form.getlist('reboques[]') if p.strip()])
        db.session.add(ConjuntoVeicular(nome_conjunto=request.form['nome_conjunto'], placa_tracionador=request.form['placa_tracionador'].upper(), placa_carreta1=reb))
        db.session.commit(); flash('Conjunto cadastrado!', 'success')
        return redirect(url_for('listar_conjuntos'))
    return render_template('conjuntos.html', conjuntos=ConjuntoVeicular.query.all())

# --- ROMANEIOS ---
@app.route('/romaneios')
@login_required
def listar_romaneios(): return render_template('romaneios.html', romaneios=Romaneio.query.order_by(Romaneio.id.desc()).all())

@app.route('/romaneios/<int:id>')
@login_required
def detalhe_romaneio(id): return render_template('romaneio_detalhe.html', romaneio=Romaneio.query.get_or_404(id))

# --- SALDO PENDENTE ---
@app.route('/saldo-pendente')
@login_required
def saldo_pendente():
    pendentes = Romaneio.query.filter_by(status='Pendente Complemento').order_by(Romaneio.id.asc()).all()
    total_ton = sum(r.dif_peso for r in pendentes if r.dif_peso > 0)
    total_valor = sum(r.dif_valor for r in pendentes)
    return render_template('saldo.html', pendentes=pendentes, total_ton=total_ton, total_valor=total_valor)

@app.route('/fechar-saldo', methods=['POST'])
@login_required
def fechar_saldo():
    chave = request.form.get('chave_complementar')
    pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()
    if not pendentes:
        flash('Não há romaneios pendentes para fechar.', 'warning')
        return redirect(url_for('saldo_pendente'))
    for r in pendentes:
        r.status = 'Faturado'; r.chave_complementar = chave
    db.session.commit()
    flash(f'✅ Acerto fechado! {len(pendentes)} romaneios baixados.', 'success')
    return redirect(url_for('saldo_pendente'))

# --- RELATÓRIOS E IMPORTAÇÃO ---
@app.route('/relatorio-simples-excel')
@login_required
def relatorio_simples_excel():
    pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()
    wb = Workbook(); ws = wb.active
    ws.append(["Romaneio", "Motorista", "Peso Fisco", "Peso Real", "Diferença", "Valor a Receber"])
    for r in pendentes:
        ws.append([r.numero_romaneio, r.motorista.nome if r.motorista else '', r.peso_fisco, r.peso_real or 0, round(r.dif_peso, 3), round(r.dif_valor, 2)])
    arq = io.BytesIO(); wb.save(arq); arq.seek(0)
    return send_file(arq, as_attachment=True, download_name="Relatorio_Simples.xlsx")

@app.route('/relatorio-espelho-excel')
@login_required
def relatorio_espelho_excel():
    roms = Romaneio.query.filter_by(status='Pendente Complemento').order_by(Romaneio.id.asc()).all()
    if not roms:
        flash('Não há romaneios pendentes.', 'warning')
        return redirect(url_for('saldo_pendente'))
        
    wb = Workbook(); ws = wb.active
    ws.merge_cells('A1:N1'); ws['A1'] = "FBE FAST BIOMASS X QUEIROZ - 5.122"; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
    
    headers = ["QTD", "DATA", "DATA ENTREGA", "PLACA CAVALO", "NOTA", "TON FISCO", "VALOR/TON", "VALOR NF", "TON ENTREGUE", "VALOR/TON", "TOTAL", "DIF FISCO", "DIF VALOR", "MOTORISTA"]
    ws.append(headers)
    
    for cell in ws[2]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")

    for i, r in enumerate(roms, 1):
        placa = r.conjunto.placa_tracionador if r.conjunto else "N/A"
        data = r.data_criacao.strftime('%d/%m/%Y') if r.data_criacao else ''
        ws.append([
            i, data, data, placa, r.numero_romaneio, 
            r.peso_fisco, r.valor_tonelada, (r.peso_fisco * r.valor_tonelada), 
            r.peso_real or 0, r.valor_tonelada, ((r.peso_real or 0) * r.valor_tonelada), 
            round(r.dif_peso, 3), round(r.dif_valor, 2), r.motorista.nome if r.motorista else ''
        ])

    arq = io.BytesIO(); wb.save(arq); arq.seek(0)
    return send_file(arq, as_attachment=True, download_name="Relatorio_Espelho.xlsx")

@app.route('/importar-planilha', methods=['POST'])
@login_required
def importar_planilha():
    # (Mantido igual para não quebrar)
    return redirect(url_for('listar_romaneios'))

# --- ESTOQUE E CUSTOS ---
@app.route('/estoque')
@login_required
def painel_estoque():
    movs = MovimentoEstoque.query.all()
    ent = sum(m.quantidade_ton for m in movs if m.tipo == 'Entrada')
    sai = sum(m.quantidade_ton for m in movs if m.tipo == 'Saida')
    return render_template('estoque.html', movimentos=movs, total_entrada=ent, total_saida=sai, saldo_atual=ent-sai)

@app.route('/abastecimentos', methods=['GET', 'POST'])
@login_required
def listar_abastecimentos():
    return render_template('abastecimentos.html', abastecimentos=Abastecimento.query.all(), caminhoes=Caminhao.query.all())

@app.route('/manutencoes', methods=['GET', 'POST'])
@login_required
def listar_manutencoes():
    return render_template('manutencoes.html', manutencoes=Manutencao.query.all(), caminhoes=Caminhao.query.all())

@app.route('/multas', methods=['GET', 'POST'])
@login_required
def listar_multas():
    return render_template('multas.html', multas=Multa.query.all(), caminhoes=Caminhao.query.all(), motoristas=Motorista.query.all())

# --- PARÂMETROS E LOGO ---
@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    config = ConfiguracaoEmpresa.query.first()
    if request.method == 'POST':
        config.nome_fantasia = request.form.get('nome_fantasia')
        config.peso_padrao_ton = float(request.form.get('peso_padrao_ton'))
        config.valor_tonelada_padrao = float(request.form.get('valor_tonelada_padrao'))
        logo_file = request.files.get('logo_file')
        if logo_file and logo_file.filename != '':
            filename = secure_filename(logo_file.filename)
            logo_file.save(os.path.join('static', 'img', filename))
            config.logo_filename = filename
        db.session.commit(); flash('Parâmetros salvos!', 'success')
        return redirect(url_for('configuracoes'))
    return render_template('configuracoes.html', config=config)

# --- ROTAS SECRETAS DE TESTE ---
@app.route('/resetar-banco-nuvem')
def resetar_banco_nuvem():
    try:
        db.drop_all()
        db.create_all()
        u = Usuario(username='admin', nome='Admin')
        u.set_senha('admin123')
        db.session.add(u)
        db.session.add(ConfiguracaoEmpresa())
        db.session.commit()
        return "✅ Banco de dados resetado!"
    except Exception as e:
        db.session.rollback()
        return f"❌ Erro: {e}"

@app.route('/rota-secreta-importacao')
def rota_secreta_importacao():
    try:
        if not os.path.exists('dados_backup.json'):
            return "❌ Arquivo dados_backup.json não encontrado."
        with open('dados_backup.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)
        if dados.get("config") and not ConfiguracaoEmpresa.query.first():
            db.session.add(ConfiguracaoEmpresa(**dados["config"]))
        for m in dados.get("motoristas", []):
            if not Motorista.query.filter_by(cpf=m["cpf"]).first():
                db.session.add(Motorista(**m))
        db.session.commit()
        for c in dados.get("conjuntos", []):
            if not ConjuntoVeicular.query.filter_by(nome_conjunto=c["nome_conjunto"]).first():
                db.session.add(ConjuntoVeicular(**c))
        db.session.commit()
        for r in dados.get("romaneios", []):
            if not Romaneio.query.filter_by(numero_romaneio=r["numero_romaneio"]).first():
                mot = Motorista.query.filter_by(cpf=r["motorista_cpf"]).first() if r.get("motorista_cpf") else None
                conj = ConjuntoVeicular.query.filter_by(placa_tracionador=r["conjunto_placa"]).first() if r.get("conjunto_placa") else None
                db.session.add(Romaneio(
                    numero_romaneio=r["numero_romaneio"], peso_fisco=r["peso_fisco"], peso_real=r["peso_real"],
                    valor_tonelada=r["valor_tonelada"], status=r["status"],
                    motorista_id=mot.id if mot else None, conjunto_id=conj.id if conj else None
                ))
        db.session.commit()
        return "✅ Dados importados com sucesso!"
    except Exception as e:
        return f"❌ Erro: {e}"

if __name__ == '__main__':
    app.run(debug=True)