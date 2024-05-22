from datetime import datetime
from tradepilot import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    user_data = db.relationship('UserData', backref='owner', lazy=True)

class UserData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    min_trading_days = db.Column(db.String(255))
    max_daily_loss = db.Column(db.String(255))
    max_loss = db.Column(db.String(255))
    profit_target = db.Column(db.String(255))
    instrument = db.Column(db.String(255))
    trading_session = db.Column(db.String(255))
    risk_reward = db.Column(db.String(255))
    daily_max_loss = db.Column(db.String(255))
    consecutive_losers = db.Column(db.String(255))
    trading_strategy = db.Column(db.String(255))
    timeframes = db.Column(db.String(255))
    trades_per_day = db.Column(db.String(255))
