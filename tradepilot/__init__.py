from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'af4f41d883e5c91089432256fbf47ec562bdf45f35e7906f'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/tradepilot'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)

from tradepilot import routes, models
