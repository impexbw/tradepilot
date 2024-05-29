import os
from flask import render_template, url_for, jsonify, flash, redirect, request
from datetime import datetime, timedelta 
from tradepilot import app, db, bcrypt
from tradepilot.forms import RegistrationForm, LoginForm, UserDataForm, TradeForm
from tradepilot.models import User, UserData, Trade
from flask_login import login_user, current_user, logout_user, login_required
from decimal import Decimal
from werkzeug.utils import secure_filename
import logging

def recalculate_equity(user_data):
    """Recalculate equity based on all trades."""
    trades = Trade.query.filter_by(user_id=user_data.user_id).all()
    total_profit = sum(Decimal(trade.profit) for trade in trades)
    user_data.equity = Decimal(user_data.balance) + total_profit
    logging.debug(f"Recalculated equity: {user_data.equity}")
    db.session.commit()

def update_equity(user_data, profit_delta):
    """Update user equity based on profit delta."""
    if not isinstance(user_data.equity, Decimal):
        user_data.equity = Decimal(user_data.equity)
    user_data.equity += Decimal(profit_delta)
    logging.debug(f"Updated equity: {user_data.equity}")
    db.session.commit()

def sync_balance_from_equity(user_data):
    """Update user balance from equity at the start of a new day."""
    current_date = datetime.now().date()
    if user_data.last_update_date != current_date:
        user_data.balance = user_data.equity
        user_data.last_update_date = current_date
        logging.debug(f"Updated balance: {user_data.balance} on {current_date}")
        db.session.commit()

def handle_trade_update(user_data, old_profit, new_profit):
    """Handle trade update, adjusting equity accordingly."""
    profit_delta = Decimal(new_profit) - Decimal(old_profit)
    update_equity(user_data, profit_delta)

def handle_trade_removal(user_data, trade_profit):
    """Handle trade removal, adjusting equity accordingly."""
    update_equity(user_data, -Decimal(trade_profit))

def calculate_equity_and_balance(user_data):
    trades = Trade.query.filter_by(user_id=user_data.user_id).all()
    total_profit = sum(Decimal(trade.profit) for trade in trades)
    equity = Decimal(user_data.balance) + total_profit
    return Decimal(user_data.balance), equity

def calculate_max_drawdown(trades):
    equity_curve = [0]  # Starting with zero for initial equity
    for trade in trades:
        equity_curve.append(equity_curve[-1] + float(trade.profit))
    peak = equity_curve[0]
    max_drawdown = 0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = peak - value
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown

def calculate_average_rrr(trades):
    total_rrr = 0
    count = 0
    for trade in trades:
        if trade.t_p and trade.s_l and trade.price:
            rrr = abs(float(trade.t_p) - float(trade.price)) / abs(float(trade.s_l) - float(trade.price)) if trade.s_l != trade.price else 0
            total_rrr += rrr
            count += 1
    return total_rrr / count if count > 0 else 0

def calculate_expectancy(trades):
    total_profit = sum(float(trade.profit) for trade in trades)
    return total_profit / len(trades) if trades else 0

def calculate_profit_factor(trades):
    total_gains = sum(float(trade.profit) for trade in trades if trade.profit > 0)
    total_losses = abs(sum(float(trade.profit) for trade in trades if trade.profit < 0))
    return total_gains / total_losses if total_losses > 0 else 0

def calculate_sharpe_ratio(trades, risk_free_rate=0.02):
    returns = [float(trade.profit) for trade in trades]
    avg_return = sum(returns) / len(returns) if returns else 0
    std_dev = (sum([(x - avg_return) ** 2 for x in returns]) / len(returns)) ** 0.5 if returns else 1
    return (avg_return - risk_free_rate) / std_dev if std_dev != 0 else 0

def get_daily_summary(trades):
    summary = {}
    for trade in trades:
        trade_date = trade.open_time.date()
        if trade_date not in summary:
            summary[trade_date] = {'trades': 0, 'lots': 0, 'result': 0}
        summary[trade_date]['trades'] += 1
        summary[trade_date]['lots'] += float(trade.size)
        summary[trade_date]['result'] += float(trade.profit)
    return [{'date': date, 'trades': data['trades'], 'lots': data['lots'], 'result': data['result']} for date, data in sorted(summary.items(), reverse=True)]

@app.route('/')
@app.route('/dashboard')
@login_required
def index():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    
    if user_data:
        # Update balance from equity at the start of a new day
        sync_balance_from_equity(user_data)
        # Initial sync if equity has not been calculated yet
        if user_data.equity is None:
            recalculate_equity(user_data)
    
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

    # Calculate dynamic balance and equity
    balance, equity = calculate_equity_and_balance(user_data) if user_data else (Decimal(0), Decimal(0))

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
                           equity=equity,  # Dynamic calculation
                           balance=balance)  # Dynamic calculation

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

            # Recalculate equity for the user on login
            user_data = UserData.query.filter_by(user_id=user.id).first()
            if user_data:
                recalculate_equity(user_data)

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
        user_data.broker_name = form.broker_name.data
        user_data.platform = form.platform.data
        user_data.equity = form.equity.data
        user_data.balance = form.balance.data
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
        form.broker_name.data = user_data.broker_name
        form.platform.data = user_data.platform
        form.equity.data = user_data.equity
        form.balance.data = user_data.balance
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
    return render_template('edit.html', form=form, user_data=user_data)


@app.route('/daily')
@login_required
def daily():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    return render_template('daily.html', user_data=user_data)

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'filename': filename}), 200
    return jsonify({'error': 'File not allowed'}), 400

@app.route('/add_trade', methods=['GET', 'POST'])
@login_required
def add_trade():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    if not user_data or user_data.balance is None or user_data.equity is None:
        flash('Please set your balance and equity before adding a trade.', 'warning')
        return redirect(url_for('edit'))  # Redirect to the edit page where the flash message will be shown

    form = TradeForm()
    if form.validate_on_submit():
        uploaded_files = request.form.getlist('uploaded_files[]')
        new_trade = Trade(
            user_id=current_user.id,
            ticket=form.ticket.data,
            open_time=form.open_time.data,
            close_time=form.close_time.data,
            trade_type=form.trade_type.data,
            size=form.size.data,
            item=form.item.data,
            price=form.price.data,
            s_l=form.s_l.data,
            t_p=form.t_p.data,
            close_price=form.close_price.data,
            comm=form.comm.data,
            taxes=form.taxes.data,
            swap=form.swap.data,
            profit=form.profit.data,
            comments=form.comments.data,
            strategy=form.strategy.data,
            screenshot1=uploaded_files[0] if len(uploaded_files) > 0 else None,
            screenshot2=uploaded_files[1] if len(uploaded_files) > 1 else None,
            screenshot3=uploaded_files[2] if len(uploaded_files) > 2 else None
        )
        new_trade.calculate_pips()
        new_trade.calculate_duration()
        db.session.add(new_trade)
        db.session.commit()

        # Update equity after adding a new trade
        user_data = UserData.query.filter_by(user_id=current_user.id).first()
        if user_data:
            update_equity(user_data, new_trade.profit)
            sync_balance_from_equity(user_data)  # Sync balance if necessary

        flash('Your trade has been added!', 'success')
        return redirect(url_for('index'))
    return render_template('add_trade.html', title='Add Trade', form=form)

@app.route('/edit_trade/<int:trade_id>', methods=['GET', 'POST'])
@login_required
def edit_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    form = TradeForm(obj=trade)
    if form.validate_on_submit():
        trade.ticket = form.ticket.data
        trade.open_time = form.open_time.data
        trade.trade_type = form.trade_type.data
        trade.size = form.size.data
        trade.item = form.item.data
        trade.price = form.price.data
        trade.s_l = form.s_l.data
        trade.t_p = form.t_p.data
        trade.close_time = form.close_time.data
        trade.close_price = form.close_price.data
        trade.comm = form.comm.data
        trade.taxes = form.taxes.data
        trade.swap = form.swap.data
        trade.profit = form.profit.data
        trade.comments = form.comments.data
        trade.strategy = form.strategy.data

        uploaded_files = request.form.getlist('uploaded_files[]')
        trade.screenshot1 = uploaded_files[0] if len(uploaded_files) > 0 else trade.screenshot1
        trade.screenshot2 = uploaded_files[1] if len(uploaded_files) > 1 else trade.screenshot2
        trade.screenshot3 = uploaded_files[2] if len(uploaded_files) > 2 else trade.screenshot3

        trade.calculate_pips()
        trade.calculate_duration()
        db.session.commit()

        # Update equity after editing a trade
        user_data = UserData.query.filter_by(user_id=current_user.id).first()
        if user_data:
            handle_trade_update(user_data, old_profit, trade.profit)
            sync_balance_from_equity(user_data)  # Sync balance if necessary

        flash('Your trade has been updated!', 'success')
        return redirect(url_for('trades'))
    return render_template('edit_trade.html', title='Edit Trade', form=form, trade=trade)

@app.route('/view_trade/<int:trade_id>', methods=['GET'])
@login_required
def view_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    return render_template('view_trade.html', title='View Trade', trade=trade)

@app.route('/trade/delete/<int:trade_id>', methods=['POST'])
@login_required
def delete_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if trade.user_id != current_user.id:
        abort(403)

    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    if user_data:
        handle_trade_removal(user_data, trade.profit)

    db.session.delete(trade)
    db.session.commit()
    flash('Your trade has been deleted!', 'success')
    return redirect(url_for('trades'))

@app.route('/trades', methods=['GET', 'POST'])
@login_required
def trades():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        # Get the date range from the form
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        ticket = request.form.get('ticket')
        trade_type = request.form.get('trade_type')
        
        query = Trade.query.filter_by(user_id=current_user.id)
        
        if start_date_str and end_date_str:
            # Convert date strings to datetime objects
            start_date = datetime.strptime(start_date_str, '%m/%d/%Y')
            end_date = datetime.strptime(end_date_str, '%m/%d/%Y') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Trade.open_time >= start_date, Trade.open_time <= end_date)
        
        if ticket:
            query = query.filter(Trade.ticket.like(f'%{ticket}%'))
        
        if trade_type:
            query = query.filter(Trade.trade_type.ilike(f'%{trade_type}%'))
        
        user_trades = query.order_by(Trade.open_time.desc()).all()
    else:
        user_trades = Trade.query.filter_by(user_id=current_user.id).order_by(Trade.open_time.desc()).all()
    
    return render_template('trades.html', trades=user_trades, user_data=user_data)

@app.route('/delete_file', methods=['POST'])
@login_required
def delete_file():
    data = request.get_json()
    filename = data.get('filename')
    trade_id = data.get('trade_id')
    
    if not filename or not trade_id:
        app.logger.error('Invalid request: Missing filename or trade_id')
        return jsonify({'error': 'Invalid request'}), 400

    trade = Trade.query.get_or_404(trade_id)

    # Ensure the current user owns the trade
    if trade.user_id != current_user.id:
        app.logger.error(f'User {current_user.id} does not own trade {trade_id}')
        abort(403)

    # Determine which screenshot field to clear
    screenshot_field = None
    if trade.screenshot1 == filename:
        trade.screenshot1 = None
    elif trade.screenshot2 == filename:
        trade.screenshot2 = None
    elif trade.screenshot3 == filename:
        trade.screenshot3 = None
    else:
        app.logger.error(f'File {filename} not found in trade {trade_id}')
        return jsonify({'error': 'File not found'}), 404

    # Commit the changes to the database
    db.session.commit()

    # Remove the file from the filesystem
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        app.logger.info(f'File {filename} removed from filesystem')
    else:
        app.logger.error(f'File {filename} not found in filesystem')

    return jsonify({'success': 'File deleted', 'screenshot_field': screenshot_field}), 200

@app.context_processor
def inject_user_data():
    if current_user.is_authenticated:
        user_data = UserData.query.filter_by(user_id=current_user.id).first()
        return dict(user_data=user_data)
    return dict(user_data=None)
