from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, DateTimeField, IntegerField, DecimalField, SelectField, TextAreaField, FileField
from wtforms.validators import DataRequired, Length, Email, EqualTo, NumberRange, ValidationError, Optional
from flask_wtf.file import FileField, FileAllowed
from tradepilot.models import ChecklistCategory, User
from flask_login import current_user


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), EqualTo('confirm_password', message='Passwords must match')])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already in use. Please choose a different one or log in.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class UpdateProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    full_name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    mood = SelectField('Mood', choices=[('😀', '😀 Happy'), ('😢', '😢 Sad'), ('😡', '😡 Angry'), ('😎', '😎 Cool'), ('😜', '😜 Playful')], validators=[DataRequired()])
    password = PasswordField('New Password', validators=[EqualTo('confirm_password', message='Passwords must match')])
    confirm_password = PasswordField('Confirm New Password')
    submit = SubmitField('Update Profile')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is taken. Please choose a different one.')

class UserDataForm(FlaskForm):
    broker_name = StringField('Broker Name', validators=[DataRequired()])
    platform = SelectField('Platform', choices=[('MT4', 'MT4'), ('MT5', 'MT5'), ('DxTrade', 'DxTrade'), ('Ctrader', 'Ctrader')], validators=[DataRequired()])
    equity = DecimalField('Equity', validators=[DataRequired(), NumberRange(min=0)], places=2)
    balance = DecimalField('Balance', validators=[DataRequired(), NumberRange(min=0)], places=2)
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
    comments = TextAreaField('Comments', validators=[Optional()])
    strategy = StringField('Strategy', validators=[Optional()])
    submit = SubmitField('Add Trade')

    def validate_close_time(form, field):
        if field.data and field.data < form.open_time.data:
            raise ValidationError('Close Time must be after Open Time')
        
class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired()])
    submit = SubmitField('Add Category')

class ItemForm(FlaskForm):
    text = StringField('Item Text', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Add Item')

    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        self.category_id.choices = [(category.id, category.name) for category in ChecklistCategory.query.all()]