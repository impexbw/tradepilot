from flask import render_template, url_for, flash, redirect, request
from tradepilot import app, db, bcrypt
from tradepilot.forms import RegistrationForm, LoginForm, UserDataForm
from tradepilot.models import User, UserData
from flask_login import login_user, current_user, logout_user, login_required

@app.route('/')
@app.route('/dashboard')
@login_required
def index():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    return render_template('index.html', user_data=user_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/forgot_password')
def forgot_password():
    flash('Password recovery is not implemented yet.', 'info')
    return redirect(url_for('login'))

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    if not user_data:
        user_data = UserData(user_id=current_user.id)
    form = UserDataForm()
    if form.validate_on_submit():
        user_data.min_trading_days = form.min_trading_days.data
        user_data.max_daily_loss = form.max_daily_loss.data
        user_data.max_loss = form.max_loss.data
        user_data.profit_target = form.profit_target.data
        user_data.instrument = form.instrument.data
        user_data.trading_session = form.trading_session.data
        user_data.risk_reward = form.risk_reward.data
        user_data.daily_max_loss = form.daily_max_loss.data
        user_data.consecutive_losers = form.consecutive_losers.data
        user_data.trading_strategy = form.trading_strategy.data
        user_data.timeframes = form.timeframes.data
        user_data.trades_per_day = form.trades_per_day.data
        db.session.add(user_data)
        db.session.commit()
        flash('Your data has been updated!', 'success')
        return redirect(url_for('index'))
    elif request.method == 'GET':
        form.min_trading_days.data = user_data.min_trading_days
        form.max_daily_loss.data = user_data.max_daily_loss
        form.max_loss.data = user_data.max_loss
        form.profit_target.data = user_data.profit_target
        form.instrument.data = user_data.instrument
        form.trading_session.data = user_data.trading_session
        form.risk_reward.data = user_data.risk_reward
        form.daily_max_loss.data = user_data.daily_max_loss
        form.consecutive_losers.data = user_data.consecutive_losers
        form.trading_strategy.data = user_data.trading_strategy
        form.timeframes.data = user_data.timeframes
        form.trades_per_day.data = user_data.trades_per_day
    return render_template('edit.html', form=form)

@app.route('/daily')
@login_required
def daily():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    return render_template('daily.html', user_data=user_data)

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')
