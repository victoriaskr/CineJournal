from flask import Flask
from flask_login import LoginManager

from app.config import Config
from flask_bootstrap import Bootstrap5

app = Flask(__name__, template_folder='templates')
app.config.from_object(Config)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
bootstrap = Bootstrap5(app)

from app import routes