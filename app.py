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

# --- INICIALIZAÇÃO BLINDADA ---
with app.app_context():
    db.create_all()
    try:
        if not Usuario.query.filter_by(username='admin').first():
            u = Usuario(username='admin', nome='Admin')
            u.set_senha('admin123')
            db.session.add(u)
            db.session.commit()
    except Exception as e:
        print(f"Aviso usuario: {e}")

    try:
        if not ConfiguracaoEmpresa.query.first():
            db.session.add(ConfiguracaoEmpresa())
            db.session.commit()
    except Exception as e:
        print(f"Aviso config: {e}")

@app.context_processor
def inject_globals():
    nome_empresa = 'MTI Frotas'
    try:
        config = ConfiguracaoEmpresa.query.first()
        if config:
            nome_empresa = config.nome_fantasia
    except Exception:
        pass 
        
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

# --- SALDO PENDENTE E RELATÓRIOS ---
@app.route('/saldo-pendente')
@login_required
def saldo_pendente():
    try:
        pendentes = Romaneio.query.filter_by(status='Pendente Complemento').order_by(Romaneio.id.asc()).all()
        total_ton = sum(r.dif_peso for r in pendentes if r.dif_peso > 0)
        total_valor = sum(r.dif_valor for r in pendentes)
        return render_template('saldo.html', pendentes=pendentes, total_ton=total_ton, total_valor=total_valor)
    except Exception as e:
        flash(f'Erro ao carregar saldo: {e}', 'danger')
        return redirect(url_for('index'))

@app.route('/fechar-saldo', methods=['POST'])
@login_required
def fechar_saldo():
    chave = request.form.get('chave_complementar')
    pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()
    if not pendentes:
        flash('Não há romaneios pendentes.', 'warning')
        return redirect(url_for('saldo_pendente'))
    for r in pendentes:
        r.status = 'Faturado'; r.chave_complementar = chave
    db.session.commit()
    flash(f'✅ Acerto fechado! {len(pendentes)} romaneios baixados.', 'success')
    return redirect(url_for('saldo_pendente'))

@app.route('/relatorio-saldo-pdf')
@login_required
def relatorio_saldo_pdf():
    try:
        pendentes = Romaneio.query.filter_by(status='Pendente Complemento').order_by(Romaneio.id.asc()).all()
        if not pendentes:
            flash('Não há romaneios pendentes.', 'warning')
            return redirect(url_for('saldo_pendente'))

        config = ConfiguracaoEmpresa.query.first()
        logo_filename = config.logo_filename if config else 'logo_padrao.png'
        total_ton = sum(r.dif_peso for r in pendentes if r.dif_peso > 0)
        total_valor = sum(r.dif_valor for r in pendentes)
        
        from services.gerador_pdf import gerar_pdf_saldo
        pdf_buffer = gerar_pdf_saldo(pendentes, total_ton, total_valor, logo_filename)
        
        return send_file(pdf_buffer, as_attachment=True, download_name="Relatorio_Saldo_Pendente.pdf", mimetype="application/pdf")
    except Exception as e:
        flash(f'Erro ao gerar PDF: {e}', 'danger')
        return redirect(url_for('saldo_pendente'))

@app.route('/relatorio-simples-excel')
@login_required
def relatorio_simples_excel():
    try:
        pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()
        wb = Workbook(); ws = wb.active
        ws.append(["Romaneio", "Motorista", "Peso Fisco", "Peso Real", "Diferença", "Valor a Receber"])
        for r in pendentes:
            ws.append([r.numero_romaneio, r.motorista.nome if r.motorista else '', r.peso_fisco, r.peso_real or 0, round(r.dif_peso, 3), round(r.dif_valor, 2)])
        arq = io.BytesIO(); wb.save(arq); arq.seek(0)
        return send_file(arq, as_attachment=True, download_name="Relatorio_Simples.xlsx")
    except Exception as e:
        flash(f'Erro: {e}', 'danger')
        return redirect(url_for('index'))

@app.route('/relatorio-espelho-excel')
@login_required
def relatorio_espelho_excel():
    try:
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
    except Exception as e:
        flash(f'Erro: {e}', 'danger')
        return redirect(url_for('index'))

# --- PARÂMETROS E LOGO ---
@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    try:
        config = ConfiguracaoEmpresa.query.first()
        if not config:
            config = ConfiguracaoEmpresa()
            db.session.add(config)
            db.session.commit()
            
        if request.method == 'POST':
            config.nome_fantasia = request.form.get('nome_fantasia', 'FBE')
            config.peso_padrao_ton = float(request.form.get('peso_padrao_ton', 45.0))
            config.valor_tonelada_padrao = float(request.form.get('valor_tonelada_padrao', 465.0))
            
            logo_file = request.files.get('logo_file')
            if logo_file and logo_file.filename != '':
                filename = secure_filename(logo_file.filename)
                logo_file.save(os.path.join('static', 'img', filename))
                config.logo_filename = filename
                
            db.session.commit(); flash('Parâmetros salvos!', 'success')
            return redirect(url_for('configuracoes'))
        return render_template('configuracoes.html', config=config)
    except Exception as e:
        flash(f'Erro nos parâmetros: {e}', 'danger')
        return redirect(url_for('index'))

# --- ESTOQUE E CUSTOS ---
@app.route('/estoque')
@login_required
def painel_estoque(): return render_template('estoque.html', movimentos=[], total_entrada=0, total_saida=0, saldo_atual=0)

@app.route('/abastecimentos')
@login_required
def listar_abastecimentos(): return render_template('abastecimentos.html', abastecimentos=[], caminhoes=[])

@app.route('/manutencoes')
@login_required
def listar_manutencoes(): return render_template('manutencoes.html', manutencoes=[], caminhoes=[])

@app.route('/multas')
@login_required
def listar_multas(): return render_template('multas.html', multas=[], caminhoes=[], motoristas=[])

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
        return "✅ Banco de dados resetado com sucesso!"
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
        
        for m in dados.get("motoristas", []):
            if not Motorista.query.filter_by(cpf=m["cpf"]).first():
                db.session.add(Motorista(**m))
        db.session.commit()
        
        for r in dados.get("romaneios", []):
            if not Romaneio.query.filter_by(numero_romaneio=r["numero_romaneio"]).first():
                mot = Motorista.query.filter_by(cpf=r["motorista_cpf"]).first() if r.get("motorista_cpf") else None
                db.session.add(Romaneio(
                    numero_romaneio=r["numero_romaneio"], peso_fisco=r["peso_fisco"], peso_real=r["peso_real"],
                    valor_tonelada=r["valor_tonelada"], status=r["status"],
                    motorista_id=mot.id if mot else None
                ))
        db.session.commit()
        return "✅ Dados importados com sucesso!"
    except Exception as e:
        return f"❌ Erro: {e}"

if __name__ == '__main__':
    app.run(debug=True)
