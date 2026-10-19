import os
from dotenv import load_dotenv

load_dotenv()

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DB_USER = os.environ.get('POSTGRES_USER')
    DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    DB_HOST = os.environ.get('POSTGRES_HOST')
    DB_PORT = os.environ.get('POSTGRES_PORT')
    DB_NAME = os.environ.get('POSTGRES_DB')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'posters')