from datetime import datetime
from sqlalchemy.dialects.mysql import DECIMAL
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

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticket = db.Column(db.String(20), nullable=False)
    open_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trade_type = db.Column(db.String(10), nullable=False)
    size = db.Column(db.Float, nullable=False)
    item = db.Column(db.String(20), nullable=False)
    price = db.Column(DECIMAL(10, 2), nullable=False)
    s_l = db.Column(DECIMAL(10, 2), nullable=False)
    t_p = db.Column(DECIMAL(10, 2), nullable=False)
    close_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    close_price = db.Column(DECIMAL(10, 2), nullable=False)
    comm = db.Column(DECIMAL(10, 2), nullable=False)
    taxes = db.Column(DECIMAL(10, 2), nullable=False)
    swap = db.Column(DECIMAL(10, 2), nullable=False)
    profit = db.Column(DECIMAL(10, 2), nullable=False)
    
    def __repr__(self):
        return f"Trade('{self.ticket}', '{self.open_time}', '{self.profit}')"
    
    taxes = db.Column(DECIMAL(10, 2), nullable=False)