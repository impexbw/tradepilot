from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo

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
