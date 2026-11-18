import os, io
import json
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from flask_migrate import Migrate

from config import Config
from models import db, Usuario, Motorista, Caminhao, ConjuntoVeicular, Romaneio, MovimentoEstoque, ConfiguracaoEmpresa, Abastecimento, Manutencao, Multa, FechamentoAcerto

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
        if config: nome_empresa = config.nome_fantasia
    except Exception: pass 
        
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
def listar_motoristas(): 
    try:
        return render_template('motoristas.html', motoristas=Motorista.query.all())
    except Exception as e:
        return f"Erro em Motoristas: {e}"

@app.route('/caminhoes')
@login_required
def listar_caminhoes(): 
    try:
        return render_template('caminhoes.html', caminhoes=Caminhao.query.all())
    except Exception as e:
        return f"Erro em Caminhões: {e}"

@app.route('/conjuntos', methods=['GET', 'POST'])
@login_required
def listar_conjuntos():
    try:
        if request.method == 'POST':
            reb = ','.join([p.upper() for p in request.form.getlist('reboques[]') if p.strip()])
            db.session.add(ConjuntoVeicular(nome_conjunto=request.form['nome_conjunto'], placa_tracionador=request.form['placa_tracionador'].upper(), placa_carreta1=reb))
            db.session.commit(); flash('Conjunto cadastrado!', 'success')
            return redirect(url_for('listar_conjuntos'))
        return render_template('conjuntos.html', conjuntos=ConjuntoVeicular.query.all())
    except Exception as e:
        return f"Erro em Conjuntos: {e}"

# --- ROMANEIOS ---
@app.route('/romaneios')
@login_required
def listar_romaneios():
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        status_filtro = request.args.get('status')
        
        query = Romaneio.query
        if data_inicio:
            query = query.filter(Romaneio.data_criacao >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim:
            query = query.filter(Romaneio.data_criacao <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        if status_filtro and status_filtro != 'Todos':
            query = query.filter(Romaneio.status == status_filtro)
            
        romaneios = query.order_by(Romaneio.id.desc()).all()
        return render_template('romaneios.html', romaneios=romaneios)
    except Exception as e:
        return f"Erro ao carregar lista de romaneios: {e}"

@app.route('/romaneios/<int:id>')
@login_required
def detalhe_romaneio(id): 
    try:
        romaneio = Romaneio.query.get_or_404(id)
        return render_template('romaneio_detalhe.html', romaneio=romaneio)
    except Exception as e:
        return f"Erro ao carregar detalhe do romaneio: {e}"

# --- SALDO PENDENTE ---
@app.route('/saldo-pendente')
@login_required
def saldo_pendente():
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        status_filtro = request.args.get('status', 'Pendente Complemento')

        query = Romaneio.query
        if data_inicio:
            query = query.filter(Romaneio.data_criacao >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim:
            query = query.filter(Romaneio.data_criacao <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        if status_filtro and status_filtro != 'Todos':
            query = query.filter(Romaneio.status == status_filtro)

        pendentes = query.order_by(Romaneio.id.asc()).all()
        
        total_ton = sum(r.dif_peso for r in pendentes if r.dif_peso > 0)
        total_valor = sum(r.dif_valor for r in pendentes if r.dif_valor > 0)
        
        return render_template('saldo.html', pendentes=pendentes, total_ton=total_ton, total_valor=total_valor)
    except Exception as e:
        return f"Erro ao carregar saldo pendente: {e}"

@app.route('/fechar-saldo', methods=['POST'])
@login_required
def fechar_saldo():
    try:
        chave = request.form.get('chave_complementar')
        pendentes = Romaneio.query.filter_by(status='Pendente Complemento').all()

        if not pendentes:
            flash('Não há romaneios pendentes para fechar.', 'warning')
            return redirect(url_for('saldo_pendente'))
            
        total_ton = sum(r.dif_peso for r in pendentes if r.dif_peso > 0)
        total_valor = sum(r.dif_valor for r in pendentes if r.dif_valor > 0)

        novo_fechamento = FechamentoAcerto(chave_nota=chave, total_toneladas=total_ton, total_valor=total_valor)
        db.session.add(novo_fechamento)

        for r in pendentes:
            r.status = 'Faturado'
            r.chave_complementar = chave
            
        db.session.commit()
        flash(f'✅ Acerto fechado! {len(pendentes)} romaneios baixados com a chave {chave}.', 'success')
        return redirect(url_for('saldo_pendente'))
    except Exception as e:
        db.session.rollback()
        return f"Erro ao fechar saldo: {e}"

# --- RESTAURAR HISTÓRICO ---
@app.route('/restaurar-historico')
def restaurar_historico():
    try:
        if not os.path.exists('dados_novembro.json'):
            return "❌ Arquivo dados_novembro.json não encontrado no servidor."
            
        with open('dados_novembro.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)

        for m in dados.get("motoristas", []):
            if not Motorista.query.filter_by(cpf=m["cpf"]).first():
                db.session.add(Motorista(**m))
        db.session.commit()

        for c in dados.get("conjuntos", []):
            if not ConjuntoVeicular.query.filter_by(placa_tracionador=c["placa_tracionador"]).first():
                db.session.add(ConjuntoVeicular(**c))
        db.session.commit()

        count = 0
        for r in dados.get("romaneios", []):
            romaneio_existente = Romaneio.query.filter_by(numero_romaneio=r["numero_romaneio"]).first()
            
            if romaneio_existente:
                count += 1
            else:
                mot = Motorista.query.filter_by(cpf=r["motorista_cpf"]).first() if r.get("motorista_cpf") else None
                conj = ConjuntoVeicular.query.filter_by(placa_tracionador=r["conjunto_placa"]).first() if r.get("conjunto_placa") else None
                data_ent = datetime.strptime(r["data_entrega"], '%Y-%m-%d').date()
                
                novo_r = Romaneio(
                    numero_romaneio=r["numero_romaneio"],
                    numero_nota_original=r["numero_nota_original"],
                    peso_fisco=r["peso_fisco"],
                    peso_real=r["peso_real"],
                    valor_tonelada=r["valor_tonelada"],
                    status=r["status"],
                    data_entrega=data_ent,
                    data_criacao=datetime.now(),
                    motorista_id=mot.id if mot else None,
                    conjunto_id=conj.id if conj else None
                )
                db.session.add(novo_r)
                count += 1
        db.session.commit()
        return f"✅ Histórico restaurado! {count} romaneios trazidos de volta ao sistema. Acesse a tela de Romaneios."
    except Exception as e:
        db.session.rollback()
        return f"❌ Erro ao restaurar: {e}"

# --- IMPORTAR XML ---
@app.route('/importar-xml-nfe', methods=['POST'])
@login_required
def importar_xml_nfe():
    try:
        arquivo = request.files.get('arquivo_xml')
        if not arquivo or not arquivo.filename.endswith('.xml'):
            flash('Envie um arquivo XML válido.', 'danger')
            return redirect(url_for('saldo_pendente'))

        xml_content = arquivo.read()
        root = ET.fromstring(xml_content)
        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
        
        nNF = root.find('.//ns:ide/ns:nNF', ns).text
        chave = root.find('.//ns:infProt/ns:chNFe', ns).text
        qCom = float(root.find('.//ns:det/ns:prod/ns:qCom', ns).text)
        vProd = float(root.find('.//ns:det/ns:prod/ns:vProd', ns).text)
        
        if abs(qCom - 45.0) > 0.01:
            pendentes = Romaneio.query.filter_by(status='Pendente Complemento').order_by(Romaneio.id.asc()).all()
            saldo_restante_nota = qCom
            total_baixado = 0.0

            for r in pendentes:
                if saldo_restante_nota <= 0: break
                
                if r.dif_peso > 0:
                    if r.dif_peso <= saldo_restante_nota:
                        r.status = 'Faturado'
                        r.chave_complementar = chave
                        saldo_restante_nota -= r.dif_peso
                        total_baixado += r.dif_peso
                    else:
                        ton_baixada = saldo_restante_nota
                        r.status = 'Faturado'
                        r.chave_complementar = chave
                        r.peso_real = r.peso_fisco + ton_baixada 
                        
                        novo_residual = Romaneio(
                            numero_romaneio=f"{r.numero_romaneio}-RES",
                            numero_nota_original=r.numero_nota_original,
                            peso_fisco=r.peso_fisco,
                            peso_real=r.peso_fisco + (r.dif_peso - ton_baixada),
                            valor_tonelada=r.valor_tonelada,
                            status='Pendente Complemento',
                            data_criacao=datetime.now(),
                            motorista_id=r.motorista_id,
                            conjunto_id=r.conjunto_id
                        )
                        db.session.add(novo_residual)
                        saldo_restante_nota = 0
                        total_baixado += ton_baixada
                        break
            
            novo_fechamento = FechamentoAcerto(chave_nota=chave, total_toneladas=total_baixado, total_valor=vProd, tipo='Complementar')
            db.session.add(novo_fechamento)
            db.session.commit()
            
            msg = f'✅ NF Complementar {nNF} importada! {total_baixado:.3f}t baixadas.'
            if saldo_restante_nota > 0:
                msg += f' Atenção: Sobraram {saldo_restante_nota:.3f}t na nota.'
            flash(msg, 'success')
        else:
            flash(f'ℹ️ NF de Venda {nNF} (45t) importada.', 'info')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao importar XML: {e}', 'danger')

    return redirect(url_for('saldo_pendente'))

# --- RELATÓRIOS ---
@app.route('/relatorio-saldo-pdf')
@login_required
def relatorio_saldo_pdf():
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        status_filtro = request.args.get('status', 'Pendente Complemento')

        query = Romaneio.query
        if data_inicio: query = query.filter(Romaneio.data_criacao >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim: query = query.filter(Romaneio.data_criacao <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        if status_filtro and status_filtro != 'Todos': query = query.filter(Romaneio.status == status_filtro)

        roms = query.order_by(Romaneio.id.asc()).all()

        if not roms:
            flash('Não há romaneios para o filtro selecionado.', 'warning')
            return redirect(url_for('saldo_pendente'))
            
        config = ConfiguracaoEmpresa.query.first()
        logo_filename = config.logo_filename if config else 'logo_padrao.png'
        
        total_ton = sum(r.dif_peso for r in roms if r.dif_peso > 0)
        total_valor = sum(r.dif_valor for r in roms if r.dif_valor > 0)
        
        from services.gerador_pdf import gerar_pdf_saldo
        pdf_buffer = gerar_pdf_saldo(roms, total_ton, total_valor, logo_filename)
        return send_file(pdf_buffer, as_attachment=True, download_name="Relatorio_Saldo_Pendente.pdf", mimetype="application/pdf")
    except Exception as e:
        return f"Erro ao gerar PDF: {e}"

@app.route('/relatorio-espelho-excel')
@login_required
def relatorio_espelho_excel():
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        status_filtro = request.args.get('status', 'Pendente Complemento')

        query = Romaneio.query
        if data_inicio: query = query.filter(Romaneio.data_criacao >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim: query = query.filter(Romaneio.data_criacao <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        if status_filtro and status_filtro != 'Todos': query = query.filter(Romaneio.status == status_filtro)

        roms = query.order_by(Romaneio.id.asc()).all()
        
        if not roms:
            flash('Não há romaneios para o filtro selecionado.', 'warning')
            return redirect(url_for('saldo_pendente'))
            
        wb = Workbook(); ws = wb.active
        ws.merge_cells('A1:N1'); ws['A1'] = "FBE FAST BIOMASS X QUEIROZ - 5.122"; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
        
        headers = ["QTD", "DATA", "DATA ENTREGA", "PLACA CAVALO", "ROMANEIO", "NOTA", "TON FISCO", "VALOR/TON", "VALOR NF", "TON ENTREGUE", "VALOR/TON", "TOTAL", "DIF FISCO", "DIF VALOR", "MOTORISTA"]
        ws.append(headers)
        for cell in ws[2]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")

        for i, r in enumerate(roms, 1):
            placa = r.conjunto.placa_tracionador if r.conjunto else "N/A"
            data_pesagem = r.data_criacao.strftime('%d/%m/%Y') if r.data_criacao else ''
            data_entrega = r.data_entrega.strftime('%d/%m/%Y') if r.data_entrega else data_pesagem 
            
            ws.append([
                i, data_pesagem, data_entrega, placa, 
                r.numero_romaneio, r.numero_nota_original or '-', 
                r.peso_fisco, r.valor_tonelada, (r.peso_fisco * r.valor_tonelada), 
                r.peso_real or 0, r.valor_tonelada, ((r.peso_real or 0) * r.valor_tonelada), 
                round(r.dif_peso, 3), round(r.dif_valor, 2), r.motorista.nome if r.motorista else ''
            ])
        arq = io.BytesIO(); wb.save(arq); arq.seek(0)
        return send_file(arq, as_attachment=True, download_name="Relatorio_Espelho.xlsx")
    except Exception as e:
        return f"Erro ao gerar Excel: {e}"

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
        return f"Erro ao gerar Excel Simples: {e}"

# --- PARÂMETROS E OUTROS ---
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
        return f"Erro em Parâmetros: {e}"

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
        return f"❌ Erro: {e}"

@app.route('/atualizar-banco-seguro')
def atualizar_banco_seguro():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE romaneios ADD COLUMN IF NOT EXISTS numero_nota_original VARCHAR(20);"))
            conn.commit()
            db.create_all()
        return "✅ Banco atualizado com sucesso!"
    except Exception as e:
        return f"❌ Erro: {e}"

if __name__ == '__main__':
    app.run(debug=True)
