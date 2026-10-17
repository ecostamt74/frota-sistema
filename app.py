import os
from datetime import datetime, date
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, session)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)

from config import Config
from models import db, Usuario, Motorista, Caminhao, NotaFiscal, Abastecimento, Manutencao, Multa
from menu_config import MENUS

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(uid):
    return Usuario.query.get(int(uid))

# Cria as pastas necessárias para o sistema rodar
os.makedirs('instance', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('logs', exist_ok=True)

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        u = Usuario(username='admin', nome='Administrador', perfil='admin')
        u.set_senha('admin123')
        db.session.add(u)
        db.session.commit()
        print('[init] Usuario admin criado: admin / admin123')

@app.context_processor
def inject_menus():
    return {'menus': MENUS, 'modo_integrado': False}

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.perfil != 'admin':
            flash('Acesso restrito.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper

# ==========================================
# AUTENTICAÇÃO
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(username=request.form['username']).first()
        if u and u.checar_senha(request.form['password']):
            login_user(u)
            return redirect(url_for('index'))
        flash('Usuario ou senha invalidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================
# PAINEL
# ==========================================
@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           total_caminhoes=Caminhao.query.count(),
                           total_motoristas=Motorista.query.count(),
                           total_notas=NotaFiscal.query.count(),
                           total_abastecimentos=Abastecimento.query.count())

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# ==========================================
# MOTORISTAS
# ==========================================
@app.route('/motoristas')
@login_required
def listar_motoristas():
    return render_template('motoristas.html', motoristas=Motorista.query.all())

@app.route('/motoristas/novo', methods=['GET', 'POST'])
@login_required
def novo_motorista():
    if request.method == 'POST':
        try:
            val = request.form.get('validade_cnh')
            m = Motorista(
                nome=request.form.get('nome', '').upper(),
                cpf=request.form.get('cpf'),
                cnh=request.form.get('cnh'),
                categoria=request.form.get('categoria'),
                validade_cnh=datetime.strptime(val, '%Y-%m-%d').date() if val else None,
                telefone=request.form.get('telefone')
            )
            db.session.add(m)
            db.session.commit()
            flash('Motorista cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_motoristas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar: {e}', 'danger')
    return render_template('form_motorista.html')

# ==========================================
# CAMINHÕES
# ==========================================
@app.route('/caminhoes')
@login_required
def listar_caminhoes():
    return render_template('caminhoes.html', caminhoes=Caminhao.query.all())

@app.route('/caminhoes/novo', methods=['GET', 'POST'])
@login_required
def novo_caminhao():
    if request.method == 'POST':
        try:
            placa = request.form.get('placa', '').upper().replace('-', '').replace(' ', '')
            c = Caminhao(
                placa=placa,
                marca=request.form.get('marca'),
                modelo=request.form.get('modelo'),
                ano=int(request.form.get('ano')) if request.form.get('ano') else None,
                km_atual=int(request.form.get('km_atual') or 0),
                intervalo_troca_oleo=int(request.form.get('intervalo_troca_oleo') or 10000)
            )
            db.session.add(c)
            db.session.commit()
            flash('Caminhão cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_caminhoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar: {e}', 'danger')
    return render_template('form_caminhao.html')

# ==========================================
# IMPORTAÇÃO VIA EXCEL (100% FUNCIONAL)
# ==========================================
@app.route('/importar', methods=['GET', 'POST'])
@login_required
def importar_excel():
    if request.method == 'POST':
        arquivo = request.files.get('arquivo')
        if arquivo and arquivo.filename.endswith('.xlsx'):
            from werkzeug.utils import secure_filename
            # Importa a função da pasta services que criamos
            from services.importador_excel import importar_motoristas, importar_caminhoes
            
            caminho = os.path.join('uploads', secure_filename(arquivo.filename))
            arquivo.save(caminho)
            
            try:
                msg_mot = importar_motoristas(caminho)
                msg_cam = importar_caminhoes(caminho)
                flash(f'✅ {msg_mot} | {msg_cam}', 'success')
            except Exception as e:
                flash(f'❌ Erro na importação: {str(e)}', 'danger')
        else:
            flash('❌ Envie um arquivo .xlsx válido.', 'danger')
            
        return redirect(url_for('importar_excel'))
    
    return render_template('importar.html')

# ==========================================
# OUTRAS ROTAS (Planejadas para as próximas etapas)
# ==========================================
@app.route('/upload-nota', methods=['GET', 'POST'])
@login_required
def upload_nota():
    return render_template('upload_nota.html', notas=[])

@app.route('/historico')
@login_required
def historico():
    return render_template('historico.html', notas=[])

@app.route('/abastecimentos')
@login_required
def listar_abastecimentos():
    return render_template('abastecimentos.html', abastecimentos=[])

@app.route('/manutencoes')
@login_required
def listar_manutencoes():
    return render_template('manutencoes.html', manutencoes=[], caminhoes=Caminhao.query.all())

@app.route('/multas')
@login_required
def listar_multas():
    return render_template('multas.html', multas=[], caminhoes=Caminhao.query.all(), motoristas=Motorista.query.all())

@app.route('/empresas')
@login_required
@admin_required
def listar_empresas():
    return render_template('empresas.html', empresas=[])

@app.route('/lgpd')
def lgpd_info():
    return render_template('lgpd.html')

@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    print()
    print('=' * 60)
    print('  SISTEMA DE FROTA - Rodando em http://localhost:5000')
    print('=' * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)