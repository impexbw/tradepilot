import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_dropzone import Dropzone
from .celery import make_celery

app = Flask(__name__)
app._static_folder = '../static'
app.config['SECRET_KEY'] = 'af4f41d883e5c91089432256fbf47ec562bdf45f35e7906f'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/tradepilot'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, '../static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Dropzone settings
app.config['DROPZONE_UPLOAD_MULTIPLE'] = True
app.config['DROPZONE_ALLOWED_FILE_TYPE'] = 'image'
app.config['DROPZONE_MAX_FILE_SIZE'] = 3  # 3 MB
app.config['DROPZONE_MAX_FILES'] = 6

# Ensure the upload directory exists
upload_dir = app.config['UPLOAD_FOLDER']
if not os.path.exists(upload_dir):
    os.makedirs(upload_dir)

# Celery configuration with new settings
app.config['broker_url'] = 'redis://localhost:6379/0'
app.config['result_backend'] = 'redis://localhost:6379/0'
app.config['imports'] = ('tradepilot.tasks',)
app.config['beat_schedule'] = {
    'update-equity-every-5-minutes': {
        'task': 'tradepilot.tasks.update_all_users_balance',
        'schedule': 300.0,  # Every 5 minutes
    },
}

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'user.login'
migrate = Migrate(app, db)
dropzone = Dropzone(app)

celery = make_celery(app)

from tradepilot.user_routes import user_bp  # Import the user blueprint

# Register the blueprint
app.register_blueprint(user_bp, url_prefix='/')

# Custom filter to use getattr in Jinja2
@app.template_filter()
def get_attr(obj, attr):
    return getattr(obj, attr)

app.jinja_env.filters['get_attr'] = get_attr
