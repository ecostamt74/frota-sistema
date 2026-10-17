from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
import bcrypt

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(120))
    senha_hash = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(20), default='operador')
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = bcrypt.hashpw(senha.encode('utf-8'),
                                        bcrypt.gensalt()).decode('utf-8')

    def checar_senha(self, senha):
        try:
            return bcrypt.checkpw(senha.encode('utf-8'),
                                  self.senha_hash.encode('utf-8'))
        except Exception:
            return False

    def is_admin(self):
        return self.perfil == 'admin'


class Motorista(db.Model):
    __tablename__ = 'motoristas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    cnh = db.Column(db.String(20))
    categoria = db.Column(db.String(5))
    validade_cnh = db.Column(db.Date)
    telefone = db.Column(db.String(20))
    pontos_cnh = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    origem = db.Column(db.String(20), default='manual')
    importado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def cnh_vencida(self):
        return self.validade_cnh and self.validade_cnh < date.today()


class Caminhao(db.Model):
    __tablename__ = 'caminhoes'
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False, index=True)
    modelo = db.Column(db.String(50))
    marca = db.Column(db.String(50))
    ano = db.Column(db.Integer)
    renavam = db.Column(db.String(15))
    km_atual = db.Column(db.Integer, default=0)
    km_ultima_troca_oleo = db.Column(db.Integer, default=0)
    intervalo_troca_oleo = db.Column(db.Integer, default=10000)
    status = db.Column(db.String(20), default='Ativo')
    origem = db.Column(db.String(20), default='manual')
    importado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def proxima_troca_oleo(self):
        return (self.km_ultima_troca_oleo or 0) + (self.intervalo_troca_oleo or 10000)

    def precisa_trocar_oleo(self):
        return (self.km_atual or 0) >= self.proxima_troca_oleo()

    def falta_km_oleo(self):
        return max(0, self.proxima_troca_oleo() - (self.km_atual or 0))


class NotaFiscal(db.Model):
    __tablename__ = 'notas_fiscais'
    id = db.Column(db.Integer, primary_key=True)
    numero_nf = db.Column(db.String(30))
    chave_acesso = db.Column(db.String(60), unique=True, index=True)
    data_emissao = db.Column(db.Date)
    emitente = db.Column(db.String(150))
    placa_extraida = db.Column(db.String(10), index=True)
    km_extraido = db.Column(db.Integer)
    litros = db.Column(db.Float)
    valor_total = db.Column(db.Float)
    observacao = db.Column(db.Text)
    arquivo = db.Column(db.String(200))
    formato = db.Column(db.String(10))
    origem = db.Column(db.String(20), default='manual')
    importado_em = db.Column(db.DateTime, default=datetime.utcnow)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'))
    caminhao = db.relationship('Caminhao', backref='notas')


class Abastecimento(db.Model):
    __tablename__ = 'abastecimentos'
    id = db.Column(db.Integer, primary_key=True)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'), nullable=False)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    nota_id = db.Column(db.Integer, db.ForeignKey('notas_fiscais.id'))
    data = db.Column(db.Date, default=date.today)
    km_hodometro = db.Column(db.Integer, nullable=False)
    litros = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float)
    posto = db.Column(db.String(120))
    origem = db.Column(db.String(20), default='manual')
    caminhao = db.relationship('Caminhao', backref='abastecimentos')
    motorista = db.relationship('Motorista')
    nota = db.relationship('NotaFiscal')


class Manutencao(db.Model):
    __tablename__ = 'manutencoes'
    id = db.Column(db.Integer, primary_key=True)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    data_servico = db.Column(db.Date, default=date.today)
    km_servico = db.Column(db.Integer)
    km_proxima = db.Column(db.Integer)
    data_proxima = db.Column(db.Date)
    valor = db.Column(db.Float)
    oficina = db.Column(db.String(120))
    descricao = db.Column(db.Text)
    origem = db.Column(db.String(20), default='manual')
    caminhao = db.relationship('Caminhao', backref='manutencoes')


class Multa(db.Model):
    __tablename__ = 'multas'
    id = db.Column(db.Integer, primary_key=True)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'), nullable=False)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    numero_auto = db.Column(db.String(40), unique=True)
    data_infracao = db.Column(db.Date)
    local = db.Column(db.String(200))
    tipo_infracao = db.Column(db.String(200))
    codigo_ctb = db.Column(db.String(10))
    valor = db.Column(db.Float, nullable=False)
    pontos = db.Column(db.Integer, default=0)
    vencimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pendente')
    observacao = db.Column(db.Text)
    origem = db.Column(db.String(20), default='manual')
    caminhao = db.relationship('Caminhao', backref='multas')
    motorista = db.relationship('Motorista', backref='multas')
