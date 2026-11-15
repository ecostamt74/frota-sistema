from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
import bcrypt

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(120))
    def set_senha(self, senha): self.senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    def checar_senha(self, senha): return bcrypt.checkpw(senha.encode('utf-8'), self.senha_hash.encode('utf-8'))

class Motorista(db.Model):
    __tablename__ = 'motoristas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    cnh = db.Column(db.String(20))

class Caminhao(db.Model):
    __tablename__ = 'caminhoes'
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    marca = db.Column(db.String(50))
    modelo = db.Column(db.String(50))

class ConjuntoVeicular(db.Model):
    __tablename__ = 'conjuntos_veiculares'
    id = db.Column(db.Integer, primary_key=True)
    nome_conjunto = db.Column(db.String(50), unique=True)
    placa_tracionador = db.Column(db.String(10), nullable=False)
    # CAMPO CORRIGIDO: Aumentado para 100 caracteres para caber várias placas
    placa_carreta1 = db.Column(db.String(100)) 

class Romaneio(db.Model):
    __tablename__ = 'romaneios'
    id = db.Column(db.Integer, primary_key=True)
    numero_romaneio = db.Column(db.String(20), unique=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    conjunto_id = db.Column(db.Integer, db.ForeignKey('conjuntos_veiculares.id'))
    chave_transf = db.Column(db.String(60))
    chave_venda = db.Column(db.String(60))
    chave_complementar = db.Column(db.String(60))
    peso_fisco = db.Column(db.Float, default=45.0)
    peso_real = db.Column(db.Float)
    valor_tonelada = db.Column(db.Float, default=465.0)
    status = db.Column(db.String(30), default='Aguardando Balança')
    motorista = db.relationship('Motorista')
    conjunto = db.relationship('ConjuntoVeicular')
    @property
    def dif_peso(self): return (self.peso_real - self.peso_fisco) if self.peso_real and self.peso_fisco else 0.0
    @property
    def dif_valor(self): return (self.dif_peso * self.valor_tonelada) if self.dif_peso > 0 else 0.0

class MovimentoEstoque(db.Model):
    __tablename__ = 'movimentos_estoque'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(20))
    quantidade_ton = db.Column(db.Float)
    documento_ref = db.Column(db.String(100))

class ConfiguracaoEmpresa(db.Model):
    __tablename__ = 'configuracoes_empresa'
    id = db.Column(db.Integer, primary_key=True)
    nome_fantasia = db.Column(db.String(100), default='FBE Logística')
    peso_padrao_ton = db.Column(db.Float, default=45.0)
    valor_tonelada_padrao = db.Column(db.Float, default=465.0)
    cfop_padrao = db.Column(db.String(10), default='5101')
    cst_padrao = db.Column(db.String(10), default='51')

class Abastecimento(db.Model):
    __tablename__ = 'abastecimentos'
    id = db.Column(db.Integer, primary_key=True)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'))
    data = db.Column(db.Date, default=date.today)
    litros = db.Column(db.Float)
    valor_total = db.Column(db.Float)
    km_atual = db.Column(db.Integer)
    caminhao = db.relationship('Caminhao')

class Manutencao(db.Model):
    __tablename__ = 'manutencoes'
    id = db.Column(db.Integer, primary_key=True)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'))
    data = db.Column(db.Date, default=date.today)
    tipo = db.Column(db.String(50))
    valor = db.Column(db.Float)
    caminhao = db.relationship('Caminhao')

class Multa(db.Model):
    __tablename__ = 'multas'
    id = db.Column(db.Integer, primary_key=True)
    caminhao_id = db.Column(db.Integer, db.ForeignKey('caminhoes.id'))
    motorista_id = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    data = db.Column(db.Date, default=date.today)
    valor = db.Column(db.Float)
    pontos = db.Column(db.Integer)
    caminhao = db.relationship('Caminhao')
    motorista = db.relationship('Motorista')

class LogAuditoria(db.Model):
    __tablename__ = 'logs_auditoria'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50))
    acao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.utcnow)