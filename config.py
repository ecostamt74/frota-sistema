import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-troque-em-producao-123456')
    _db_url = os.environ.get('DATABASE_URL',
                             f'sqlite:///{os.path.join(BASE_DIR, "instance", "frota.db")}')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 300}

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    FERNET_KEY = os.environ.get('FERNET_KEY', '')
    MODO = os.environ.get('MODO', 'standalone')
    FROTA_API_URL = os.environ.get('FROTA_API_URL', '')
    FROTA_API_TOKEN = os.environ.get('FROTA_API_TOKEN', '')
