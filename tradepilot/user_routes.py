from flask import Blueprint, render_template, url_for, flash, redirect, request
from tradepilot import db, bcrypt
from tradepilot.forms import RegistrationForm, LoginForm, UpdateProfileForm
from tradepilot.models import User, UserData, Trade
from flask_login import login_user, current_user, logout_user, login_required
from decimal import Decimal
from tradepilot.routes import (recalculate_equity, sync_balance_from_equity, calculate_max_drawdown,
                              calculate_average_rrr, calculate_expectancy, 
                              calculate_profit_factor, calculate_sharpe_ratio, 
                              get_daily_summary)

# Create the Blueprint for user routes
user_bp = Blueprint('user', __name__)

@user_bp.route('/')
@user_bp.route('/dashboard')
@login_required
def index():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()

    if user_data:
        # Ensure balance is updated from equity at the start of a new day
        sync_balance_from_equity(user_data)

    last_ten_trades = Trade.query.filter_by(user_id=current_user.id).order_by(Trade.open_time.desc()).limit(10).all()
    trades = Trade.query.filter_by(user_id=current_user.id).all()

    # Calculate statistics
    total_trades = len(trades)
    winning_trades = len([trade for trade in trades if trade.profit > 0])
    losing_trades = len([trade for trade in trades if trade.profit <= 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    average_profit = sum(trade.profit for trade in trades if trade.profit > 0) / winning_trades if winning_trades > 0 else 0
    average_loss = sum(trade.profit for trade in trades if trade.profit <= 0) / losing_trades if losing_trades > 0 else 0
    net_profit = sum(trade.profit for trade in trades)
    max_drawdown = calculate_max_drawdown(trades)
    average_rrr = calculate_average_rrr(trades)
    lots = sum(trade.size for trade in trades)
    expectancy = calculate_expectancy(trades)
    profit_factor = calculate_profit_factor(trades)
    sharpe_ratio = calculate_sharpe_ratio(trades)

    # Daily summary
    daily_summaries = get_daily_summary(trades)

    # Use database values for balance and equity and format to 2 decimal places
    balance = round(user_data.balance, 2) if user_data else Decimal(0)
    equity = round(user_data.equity, 2) if user_data else Decimal(0)

    # Format the values
    win_rate = f"{win_rate:.2f}%"
    average_rrr = f"{average_rrr:.2f}"
    expectancy = f"${expectancy:.2f}"
    profit_factor = f"{profit_factor:.2f}"
    sharpe_ratio = f"{sharpe_ratio:.2f}"

    return render_template('index.html',
                           user_data=user_data,
                           last_ten_trades=last_ten_trades,
                           total_trades=total_trades,
                           winning_trades=winning_trades,
                           losing_trades=losing_trades,
                           win_rate=win_rate,
                           average_profit=average_profit,
                           average_loss=average_loss,
                           net_profit=net_profit,
                           max_drawdown=max_drawdown,
                           average_rrr=average_rrr,
                           lots=lots,
                           expectancy=expectancy,
                           profit_factor=profit_factor,
                           sharpe_ratio=sharpe_ratio,
                           daily_summaries=daily_summaries,
                           equity=f"{equity:.2f}",  # Format to 2 decimal places
                           balance=f"{balance:.2f}")  # Format to 2 decimal places

@user_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('user.login'))
    return render_template('register.html', title='Register', form=form)

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)

            # Recalculate equity for the user on login
            user_data = UserData.query.filter_by(user_id=user.id).first()
            if user_data:
                recalculate_equity(user_data)

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('user.index'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.full_name = form.full_name.data
        current_user.email = form.email.data
        current_user.mood = form.mood.data
        if form.password.data:
            current_user.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('user.profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.full_name.data = current_user.full_name
        form.email.data = current_user.email
        form.mood.data = current_user.mood
    return render_template('profile.html', form=form)

@user_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('user.login'))

@user_bp.route('/forgot_password')
def forgot_password():
    flash('Password recovery is not implemented yet.', 'info')
    return redirect(url_for('user.login'))
