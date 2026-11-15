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

# --- ATIVAÇÃO DO MODO WAL (CONCORRÊNCIA) APENAS PARA SQLITE ---
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

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        u = Usuario(username='admin', nome='Admin')
        u.set_senha('admin123')
        db.session.add(u)
    if not ConfiguracaoEmpresa.query.first():
        db.session.add(ConfiguracaoEmpresa())
    db.session.commit()

@app.context_processor
def inject_globals():
    config = ConfiguracaoEmpresa.query.first()
    grupos = {}
    menus = [
        {"titulo": "📊 Painel", "endpoint": "index", "grupo": "Operação"},
        {"titulo": "📦 Romaneios", "endpoint": "listar_romaneios", "grupo": "Operação"},
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
    return {'menus_agrupados': grupos, 'nome_empresa': config.nome_fantasia if config else 'MTI Frotas'}

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

# --- MOTORISTAS ---
@app.route('/motoristas')
@login_required
def listar_motoristas(): return render_template('motoristas.html', motoristas=Motorista.query.all())

@app.route('/motoristas/novo', methods=['GET', 'POST'])
@login_required
def novo_motorista():
    if request.method == 'POST':
        try:
            db.session.add(Motorista(nome=request.form['nome'].upper(), cpf=request.form['cpf'], cnh=request.form.get('cnh')))
            db.session.commit(); flash('Motorista cadastrado!', 'success')
            return redirect(url_for('listar_motoristas'))
        except Exception as e: db.session.rollback(); flash(f'Erro: {e}', 'danger')
    return render_template('form_motorista.html')

@app.route('/motoristas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_motorista(id):
    m = Motorista.query.get_or_404(id)
    if request.method == 'POST':
        m.nome = request.form['nome'].upper(); m.cpf = request.form['cpf']; m.cnh = request.form.get('cnh')
        db.session.commit(); flash('Motorista atualizado!', 'success')
        return redirect(url_for('listar_motoristas'))
    return render_template('editar_motorista.html', motorista=m)

# --- CAMINHÕES ---
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

@app.route('/conjuntos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_conjunto(id):
    c = ConjuntoVeicular.query.get_or_404(id)
    if request.method == 'POST':
        reb = request.form.getlist('reboques[]')
        c.nome_conjunto = request.form['nome_conjunto']; c.placa_tracionador = request.form['placa_tracionador'].upper(); c.placa_carreta1 = ','.join([p.upper() for p in reb if p.strip()])
        db.session.commit(); flash('Conjunto atualizado!', 'success')
        return redirect(url_for('listar_conjuntos'))
    return render_template('editar_conjunto.html', conjunto=c)

# --- ROMANEIOS ---
@app.route('/romaneios')
@login_required
def listar_romaneios(): return render_template('romaneios.html', romaneios=Romaneio.query.order_by(Romaneio.id.desc()).all())

@app.route('/romaneios/<int:id>')
@login_required
def detalhe_romaneio(id): return render_template('romaneio_detalhe.html', romaneio=Romaneio.query.get_or_404(id))

@app.route('/romaneios/<int:id>/lancar-manual', methods=['POST'])
@login_required
def lancar_peso_manual(id):
    r = Romaneio.query.get_or_404(id)
    try:
        peso = float(request.form.get('peso_real_manual').replace(',', '.'))
        r.peso_real = peso; r.status = 'Pendente Complemento' if peso > r.peso_fisco else 'Faturado'
        db.session.commit(); flash('Peso lançado!', 'success')
    except Exception as e: flash(f'Erro: {e}', 'danger')
    return redirect(url_for('detalhe_romaneio', id=id))

@app.route('/fechar-acerto', methods=['POST'])
@login_required
def fechar_acerto():
    pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()
    chave = request.form.get('chave_complementar')
    for r in pendentes:
        r.status = 'Faturado'; r.chave_complementar = chave
    db.session.commit(); flash('Acerto Global realizado!', 'success')
    return redirect(url_for('listar_romaneios'))

@app.route('/relatorio-simples-excel')
@login_required
def relatorio_simples_excel():
    pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()
    wb = Workbook(); ws = wb.active
    ws.append(["Romaneio", "Motorista", "Peso Fisco", "Peso Real", "Diferença", "Valor a Receber"])
    for r in pendentes:
        ws.append([r.numero_romaneio, r.motorista.nome if r.motorista else '', r.peso_fisco, r.peso_real or 0, r.dif_peso, r.dif_valor])
    arq = io.BytesIO(); wb.save(arq); arq.seek(0)
    return send_file(arq, as_attachment=True, download_name="Relatorio_Simples.xlsx")

@app.route('/relatorio-espelho-excel')
@login_required
def relatorio_espelho_excel():
    roms = Romaneio.query.order_by(Romaneio.id.asc()).all()
    wb = Workbook(); ws = wb.active
    ws.merge_cells('A1:L1'); ws['A1'] = "FBE FAST BIOMASS X QUEIROZ"; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A2:G2'); ws['A2'] = "NF FISCO"; ws['A2'].font = Font(bold=True)
    ws.merge_cells('H2:L2'); ws['H2'] = "DESCARGAS"; ws['H2'].font = Font(bold=True)
    headers = ["QTD", "DATA", "PLACA", "NOTA", "TON (Fisco)", "VALOR/TON", "TOTAL NF", "TON (Real)", "PESO NA NOTA", "DIF FISCO", "DIF VALOR", "MOTORISTA"]
    ws.append(headers)
    for i, r in enumerate(roms, 1):
        ws.append([i, r.data_criacao.strftime('%d/%m/%Y'), r.conjunto.placa_tracionador if r.conjunto else '', r.numero_romaneio, r.peso_fisco, r.valor_tonelada, r.peso_fisco*r.valor_tonelada, r.peso_real or 0, r.peso_fisco, r.dif_peso, r.dif_valor, r.motorista.nome if r.motorista else ''])
    arq = io.BytesIO(); wb.save(arq); arq.seek(0)
    return send_file(arq, as_attachment=True, download_name="Relatorio_Espelho.xlsx")

@app.route('/importar-planilha', methods=['POST'])
@login_required
def importar_planilha():
    a = request.files.get('arquivo_excel')
    if a and a.filename.endswith('.xlsx'):
        c = os.path.join('uploads', 'temp_hist.xlsx'); a.save(c)
        try:
            wb = load_workbook(c, data_only=True); ws = wb.active
            importados = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0] and str(row[0]).isdigit():
                    r = Romaneio(numero_romaneio=str(row[0]), peso_real=float(row[8] or 0), status='Faturado')
                    db.session.add(r); importados += 1
            db.session.commit(); flash(f'{importados} romaneios importados!', 'success')
        except Exception as e: flash(f'Erro: {e}', 'danger')
    return redirect(url_for('listar_romaneios'))

# --- ESTOQUE ---
@app.route('/estoque')
@login_required
def painel_estoque():
    movs = MovimentoEstoque.query.all()
    ent = sum(m.quantidade_ton for m in movs if m.tipo == 'Entrada')
    sai = sum(m.quantidade_ton for m in movs if m.tipo == 'Saida')
    return render_template('estoque.html', movimentos=movs, total_entrada=ent, total_saida=sai, saldo_atual=ent-sai)

# --- CUSTOS ---
@app.route('/abastecimentos', methods=['GET', 'POST'])
@login_required
def listar_abastecimentos():
    if request.method == 'POST':
        a = Abastecimento(caminhao_id=int(request.form['caminhao_id']), data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), litros=float(request.form['litros']), valor_total=float(request.form['valor_total']), km_atual=int(request.form['km_atual']))
        db.session.add(a); db.session.commit(); return redirect(url_for('listar_abastecimentos'))
    return render_template('abastecimentos.html', abastecimentos=Abastecimento.query.all(), caminhoes=Caminhao.query.all())

@app.route('/manutencoes', methods=['GET', 'POST'])
@login_required
def listar_manutencoes():
    if request.method == 'POST':
        m = Manutencao(caminhao_id=int(request.form['caminhao_id']), data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), tipo=request.form['tipo'], valor=float(request.form['valor']))
        db.session.add(m); db.session.commit(); return redirect(url_for('listar_manutencoes'))
    return render_template('manutencoes.html', manutencoes=Manutencao.query.all(), caminhoes=Caminhao.query.all())

@app.route('/multas', methods=['GET', 'POST'])
@login_required
def listar_multas():
    if request.method == 'POST':
        m = Multa(caminhao_id=int(request.form['caminhao_id']), motorista_id=int(request.form['motorista_id']), data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), valor=float(request.form['valor']), pontos=int(request.form['pontos']))
        db.session.add(m); db.session.commit(); return redirect(url_for('listar_multas'))
    return render_template('multas.html', multas=Multa.query.all(), caminhoes=Caminhao.query.all(), motoristas=Motorista.query.all())

# --- PARÂMETROS ---
@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    config = ConfiguracaoEmpresa.query.first()
    if request.method == 'POST':
        config.nome_fantasia = request.form.get('nome_fantasia')
        config.peso_padrao_ton = float(request.form.get('peso_padrao_ton'))
        config.valor_tonelada_padrao = float(request.form.get('valor_tonelada_padrao'))
        db.session.commit(); flash('Parâmetros salvos!', 'success')
        return redirect(url_for('configuracoes'))
    return render_template('configuracoes.html', config=config)

# --- ROTA SECRETA PARA IMPORTAR OS DADOS DO JSON ---
@app.route('/rota-secreta-importacao')
def rota_secreta_importacao():
    from models import Motorista, Caminhao, ConjuntoVeicular, Romaneio, ConfiguracaoEmpresa
    try:
        if not os.path.exists('dados_backup.json'):
            return "❌ Arquivo 'dados_backup.json' não encontrado no servidor."
            
        with open('dados_backup.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)

        if dados.get("config") and not ConfiguracaoEmpresa.query.first():
            db.session.add(ConfiguracaoEmpresa(**dados["config"]))

        for m in dados.get("motoristas", []):
            if not Motorista.query.filter_by(cpf=m["cpf"]).first():
                db.session.add(Motorista(**m))
        db.session.commit()

        for c in dados.get("caminhoes", []):
            if not Caminhao.query.filter_by(placa=c["placa"]).first():
                db.session.add(Caminhao(**c))
        db.session.commit()

        for c in dados.get("conjuntos", []):
            if not ConjuntoVeicular.query.filter_by(nome_conjunto=c["nome_conjunto"]).first():
                db.session.add(ConjuntoVeicular(**c))
        db.session.commit()

        count_romaneios = 0
        for r in dados.get("romaneios", []):
            if not Romaneio.query.filter_by(numero_romaneio=r["numero_romaneio"]).first():
                mot = Motorista.query.filter_by(cpf=r["motorista_cpf"]).first() if r.get("motorista_cpf") else None
                conj = ConjuntoVeicular.query.filter_by(placa_tracionador=r["conjunto_placa"]).first() if r.get("conjunto_placa") else None
                
                novo_r = Romaneio(
                    numero_romaneio=r["numero_romaneio"], peso_fisco=r["peso_fisco"], peso_real=r["peso_real"],
                    valor_tonelada=r["valor_tonelada"], status=r["status"], chave_venda=r.get("chave_venda"),
                    motorista_id=mot.id if mot else None, conjunto_id=conj.id if conj else None
                )
                db.session.add(novo_r)
                count_romaneios += 1
        db.session.commit()
        return f"✅ Sucesso! Dados importados: {len(dados.get('motoristas', []))} motoristas, {len(dados.get('conjuntos', []))} conjuntos e {count_romaneios} romaneios novos."
    except Exception as e:
        return f"❌ Erro ao importar: {e}"

if __name__ == '__main__':
    app.run(debug=True)
