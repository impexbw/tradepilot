import os
from flask import abort, render_template, url_for, jsonify, flash, redirect, request
from datetime import datetime, timedelta
from tradepilot import app, db, bcrypt
from tradepilot.forms import RegistrationForm, LoginForm, UserDataForm, UpdateProfileForm, TradeForm, CategoryForm, ItemForm
from tradepilot.models import ChecklistCategory, ChecklistItem, User, UserData, Trade
from flask_login import login_user, current_user, logout_user, login_required
from decimal import Decimal
from werkzeug.utils import secure_filename
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Helper function to log the state of user_data
def log_user_data_state(user_data, context):
    logging.debug(f"{context} - User Data: ID = {user_data.user_id}, Balance = {user_data.balance}, Equity = {user_data.equity}, Last Update Date = {user_data.last_update_date}")

# Recalculate equity based on all trades.
def recalculate_equity(user_data):
    trades = Trade.query.filter_by(user_id=user_data.user_id).all()
    total_profit = sum(Decimal(trade.profit) for trade in trades)
    user_data.equity = Decimal(user_data.balance) + total_profit
    log_user_data_state(user_data, "After recalculate_equity")
    logging.debug(f"Recalculate equity: Total Profit = {total_profit}, New Equity = {user_data.equity}")
    db.session.commit()

# Update user equity based on profit delta.
def update_equity(user_data, profit_delta):
    if not isinstance(user_data.equity, Decimal):
        user_data.equity = Decimal(user_data.equity)
    user_data.equity += Decimal(profit_delta)
    log_user_data_state(user_data, "After update_equity")
    logging.debug(f"Update equity: Profit Delta = {profit_delta}, New Equity = {user_data.equity}")
    db.session.commit()

def sync_balance_from_equity(user_data):
    try:
        logging.debug(f"Sync balance from equity: Old Balance = {user_data.balance}, Equity = {user_data.equity}")
        user_data.balance = user_data.equity
        user_data.last_update_date = datetime.now().date()
        db.session.commit()
        logging.debug(f"New Balance = {user_data.balance}, Last Update Date = {user_data.last_update_date}")

        db.session.refresh(user_data)
        logging.debug(f"Verified Balance in DB = {user_data.balance}, Verified Equity in DB = {user_data.equity}")
    except Exception as e:
        logging.error(f"Error syncing balance from equity: {e}")
        db.session.rollback()

# Handle trade update, adjusting equity accordingly.
def handle_trade_update(user_data, old_profit, new_profit):
    profit_delta = Decimal(new_profit) - Decimal(old_profit)
    update_equity(user_data, profit_delta)

# Handle trade removal, adjusting equity accordingly.
def handle_trade_removal(user_data, trade_profit):
    update_equity(user_data, -Decimal(trade_profit))

# Calculate maximum drawdown.
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

# Calculate average risk-reward ratio (RRR).
def calculate_average_rrr(trades):
    total_rrr = 0
    count = 0
    for trade in trades:
        if trade.t_p and trade.s_l and trade.price:
            rrr = abs(float(trade.t_p) - float(trade.price)) / abs(float(trade.s_l) - float(trade.price)) if trade.s_l != trade.price else 0
            total_rrr += rrr
            count += 1
    return total_rrr / count if count > 0 else 0

# Calculate expectancy.
def calculate_expectancy(trades):
    total_profit = sum(float(trade.profit) for trade in trades)
    return total_profit / len(trades) if trades else 0

# Calculate profit factor.
def calculate_profit_factor(trades):
    total_gains = sum(float(trade.profit) for trade in trades if trade.profit > 0)
    total_losses = abs(sum(float(trade.profit) for trade in trades if trade.profit < 0))
    return total_gains / total_losses if total_losses > 0 else 0

# Calculate Sharpe ratio.
def calculate_sharpe_ratio(trades, risk_free_rate=0.02):
    returns = [float(trade.profit) for trade in trades]
    avg_return = sum(returns) / len(returns) if returns else 0
    std_dev = (sum([(x - avg_return) ** 2 for x in returns]) / len(returns)) ** 0.5 if returns else 1
    return (avg_return - risk_free_rate) / std_dev if std_dev != 0 else 0

# Generate daily summary.
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

    # Use database values for balance and equity
    balance = user_data.balance if user_data else Decimal(0)
    equity = user_data.equity if user_data else Decimal(0)

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
                           equity=equity,  # Use database value
                           balance=balance)  # Use database value


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

@app.route('/profile', methods=['GET', 'POST'])
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
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.full_name.data = current_user.full_name
        form.email.data = current_user.email
        form.mood.data = current_user.mood
    return render_template('profile.html', form=form)

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
        form.timeframes.data = form.timeframes.data
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
        update_equity(user_data, new_trade.profit)
        db.session.commit()  # Commit changes after updating equity

        flash('Your trade has been added!', 'success')
        return redirect(url_for('index'))
    return render_template('add_trade.html', title='Add Trade', form=form)

@app.route('/edit_trade/<int:trade_id>', methods=['GET', 'POST'])
@login_required
def edit_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    form = TradeForm(obj=trade)
    if form.validate_on_submit():
        old_profit = trade.profit  # Store old profit before updating

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
            db.session.commit()  # Commit changes after updating equity

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
        db.session.commit()  # Commit changes after updating equity

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

@app.route('/reset', methods=['POST'])
@login_required
def reset():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    if user_data:
        # Reset user data fields
        user_data.broker_name = ''
        user_data.platform = ''
        user_data.equity = 0.0
        user_data.balance = 0.0
        user_data.min_trading_days = None
        user_data.max_daily_loss = None
        user_data.max_loss = None
        user_data.profit_target = None
        user_data.instrument = ''
        user_data.trading_session = ''
        user_data.risk_reward = ''
        user_data.daily_max_loss = ''
        user_data.consecutive_losers = None
        user_data.trading_strategy = ''
        user_data.timeframes = ''
        user_data.trades_per_day = None
        db.session.commit()

        # Delete all trades for the user
        Trade.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

        flash('All data have been reset to default.', 'success')
    else:
        flash('No account details found to reset.', 'warning')
    return redirect(url_for('profile'))

@app.route('/checklist_settings', methods=['GET', 'POST'])
@login_required
def checklist_settings():
    category_form = CategoryForm()
    item_form = ItemForm()
    categories = ChecklistCategory.query.filter_by(user_id=current_user.id).all()
    if category_form.validate_on_submit() and 'add_category' in request.form:
        new_category = ChecklistCategory(name=category_form.name.data, user_id=current_user.id)
        db.session.add(new_category)
        db.session.commit()
        flash('New category added!', 'success')
        return redirect(url_for('checklist_settings'))
    if item_form.validate_on_submit() and 'add_item' in request.form:
        new_item = ChecklistItem(text=item_form.text.data, category_id=item_form.category_id.data)
        db.session.add(new_item)
        db.session.commit()
        flash('New item added!', 'success')
        return redirect(url_for('checklist_settings'))
    return render_template('checklist_settings.html', category_form=category_form, item_form=item_form, categories=categories)

@app.route('/trading_checklist')
@login_required
def trading_checklist():
    categories = ChecklistCategory.query.filter_by(user_id=current_user.id).all()
    return render_template('checklist.html', categories=categories)

@app.route('/delete_category/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    category = ChecklistCategory.query.get_or_404(category_id)
    if category.user_id != current_user.id:
        abort(403)
    ChecklistItem.query.filter_by(category_id=category_id).delete()
    db.session.delete(category)
    db.session.commit()
    flash('Checklist category and its items deleted', 'success')
    return redirect(url_for('checklist_settings'))

@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = ChecklistItem.query.get_or_404(item_id)
    if item.category.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash('Checklist item deleted', 'success')
    return redirect(url_for('checklist_settings'))

@app.route('/manual_update', methods=['POST'])
@login_required
def manual_update():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    if user_data:
        logging.debug(f"Before sync_balance_from_equity - User Data: ID = {user_data.user_id}, Balance = {user_data.balance}, Equity = {user_data.equity}, Last Update Date = {user_data.last_update_date}")
        sync_balance_from_equity(user_data)
        logging.debug(f"After sync_balance_from_equity - User Data: ID = {user_data.user_id}, Balance = {user_data.balance}, Equity = {user_data.equity}, Last Update Date = {user_data.last_update_date}")
        flash('Balance and Equity have been manually updated.', 'success')
    else:
        flash('User data not found.', 'danger')
    return redirect(url_for('profile'))

@app.context_processor
def inject_user_data():
    if current_user.is_authenticated:
        user_data = UserData.query.filter_by(user_id=current_user.id).first()
        return dict(user_data=user_data, current_user=current_user)
    return dict(user_data=None, current_user=None)
