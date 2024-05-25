from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, DateTimeField, IntegerField, DecimalField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, NumberRange, Optional

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class UserDataForm(FlaskForm):
    min_trading_days = IntegerField('Minimum Trading Days', validators=[DataRequired()])
    max_daily_loss = StringField('Max Daily Loss', validators=[DataRequired()])
    max_loss = StringField('Max Loss', validators=[DataRequired()])
    profit_target = StringField('Profit Target', validators=[DataRequired()])
    instrument = StringField('Instrument', validators=[DataRequired()])
    trading_session = StringField('Trading Session', validators=[DataRequired()])
    risk_reward = StringField('Risk-Reward Ratio', validators=[DataRequired()])
    daily_max_loss = StringField('Daily Max Loss', validators=[DataRequired()])
    consecutive_losers = StringField('Consecutive Losers Limit', validators=[DataRequired()])
    trading_strategy = StringField('Trading Strategy', validators=[DataRequired()])
    timeframes = StringField('Timeframes', validators=[DataRequired()])
    trades_per_day = IntegerField('Trades Per Day', validators=[DataRequired()])
    submit = SubmitField('Save')

class TradeForm(FlaskForm):
    ticket = StringField('Ticket', validators=[DataRequired()])
    open_time = DateTimeField('Open Time', format='%Y-%m-%d %H:%M:%S', validators=[DataRequired()])
    trade_type = SelectField('Trade Type', choices=[('Buy', 'Buy'), ('Sell', 'Sell')], validators=[DataRequired()])
    size = DecimalField('Size', validators=[DataRequired(), NumberRange(min=0, max=1000000)], places=2)
    item = StringField('Item', validators=[DataRequired()])
    price = DecimalField('Price', validators=[DataRequired(), NumberRange(min=0, max=1000000)], places=2)
    s_l = DecimalField('S / L', validators=[Optional(), NumberRange(min=0, max=1000000)], places=2)
    t_p = DecimalField('T / P', validators=[Optional(), NumberRange(min=0, max=1000000)], places=2)
    close_time = DateTimeField('Close Time', format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    close_price = DecimalField('Close Price', validators=[Optional(), NumberRange(min=0, max=1000000)], places=2)
    comm = DecimalField('Comm', default=0.00, validators=[Optional(), NumberRange(min=0, max=1000000)], places=2)
    taxes = DecimalField('Taxes', default=0.00, validators=[Optional(), NumberRange(min=0, max=1000000)], places=2)
    swap = DecimalField('Swap', default=0.00, validators=[Optional(), NumberRange(min=0, max=1000000)], places=2)
    profit = DecimalField('Profit', validators=[Optional()], places=2)
    submit = SubmitField('Add Trade')