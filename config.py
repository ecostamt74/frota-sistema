import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-chave-trocar-em-producao')
    
    # Pega a URL do banco da nuvem. Se não achar, usa o SQLite local.
    _db_url = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "instance", "frota.db")}')
    
    # Correção para o Render (que usa postgres:// e o SQLAlchemy precisa de postgresql://)
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False