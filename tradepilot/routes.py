import os
from flask import abort, render_template, url_for, jsonify, flash, redirect, request
from datetime import date, datetime, timedelta
from tradepilot import app, db, bcrypt
from tradepilot.forms import RegistrationForm, LoginForm, UserDataForm, UpdateProfileForm, TradeForm, CategoryForm, ItemForm, TradingPlanForm
from tradepilot.models import ChecklistCategory, ChecklistItem, User, UserData, Trade, TradingPlan
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
    logging.debug(f"Sync balance from equity: Old Balance = {user_data.balance}, Equity = {user_data.equity}")
    user_data.balance = Decimal(user_data.equity).quantize(Decimal('0.01'))
    user_data.last_update_date = datetime.now().date()
    db.session.commit()
    logging.debug(f"New Balance = {user_data.balance}, Last Update Date = {user_data.last_update_date}")

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

def calculate_average_rrr(trades, max_rrr_threshold=10):
    total_rrr = 0
    count = 0

    for trade in trades:
        try:
            # Ensure all necessary fields are present and numeric
            if all(hasattr(trade, attr) and isinstance(getattr(trade, attr), (Decimal, float, int)) for attr in ['t_p', 's_l', 'price']):
                take_profit = float(trade.t_p)
                stop_loss = float(trade.s_l)
                entry_price = float(trade.price)

                # Ensure stop_loss and entry_price are not equal to avoid division by zero
                if stop_loss != entry_price:
                    rrr = abs(take_profit - entry_price) / abs(stop_loss - entry_price)
                    # Filter out extremely high RRR values
                    if rrr <= max_rrr_threshold:
                        total_rrr += rrr
                        count += 1
        except (AttributeError, ValueError):
            # Skip trades with missing or invalid attributes
            continue

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

def get_latest_trading_plan_id(user_id):
    latest_plan = TradingPlan.query.filter_by(user_id=user_id).order_by(TradingPlan.date.desc()).first()
    return latest_plan.id if latest_plan else None

def get_today_trading_plan(user_id):
    today = date.today()
    print(f"Checking for trading plan on: {today}")  # Log today's date
    plans = TradingPlan.query.filter_by(user_id=user_id).all()
    for plan in plans:
        print(f"Existing plan date: {plan.date}, Today's date: {today}")  # Log each plan's date
        if plan.date == today:
            return plan
    return None

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
        update_equity(user_data, new_trade.profit)
        db.session.commit()  # Commit changes after updating equity

        flash('Your trade has been added!', 'success')
        return redirect(url_for('user.index'))
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
    plan_id = data.get('plan_id')
    
    if not filename or not plan_id:
        return jsonify({'error': 'Invalid data'}), 400
    
    # Assuming you have a function to delete the file from the filesystem
    delete_file_from_filesystem(filename)

    # Update the plan to remove the reference to the deleted file
    plan = TradingPlan.query.get(plan_id)
    if plan:
        if plan.image1 == filename:
            plan.image1 = None
        elif plan.image2 == filename:
            plan.image2 = None
        elif plan.image3 == filename:
            plan.image3 = None
        elif plan.image4 == filename:
            plan.image4 = None
        elif plan.image5 == filename:
            plan.image5 = None
        elif plan.image6 == filename:
            plan.image6 = None
        db.session.commit()
    
    return jsonify({'success': True})

def delete_file_from_filesystem(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Error deleting file {filename}: {e}")

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
        new_item = ChecklistItem(text=item_form.text.data, category_id=item_form.category_id.data, user_id=current_user.id)
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
    if item.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash('Checklist item deleted', 'success')
    return redirect(url_for('checklist_settings'))

@app.route('/add_trading_plan', methods=['GET', 'POST'])
@login_required
def add_trading_plan():
    existing_plan = get_today_trading_plan(current_user.id)
    if existing_plan:
        flash('A trading plan already exists for today. Please edit the existing plan.', 'warning')
        return redirect(url_for('edit_trading_plan', plan_id=existing_plan.id))
    
    form = TradingPlanForm()
    if form.validate_on_submit():
        uploaded_files = request.form.getlist('uploaded_files[]')
        plan = TradingPlan(
            user_id=current_user.id,
            date=date.today(),
            market_conditions=form.market_conditions.data,
            goals=form.goals.data,
            risk_management=form.risk_management.data,
            entry_exit_criteria=form.entry_exit_criteria.data,
            trade_setup=form.trade_setup.data,
            review_notes=form.review_notes.data,
            news_events=form.news_events.data,
            premarket_routine=form.premarket_routine.data,
            timeframe=form.timeframe.data,
            market_type=form.market_type.data,
            entries=form.entries.data,
            stop_loss=form.stop_loss.data,
            take_profit=form.take_profit.data,
            image1=uploaded_files[0] if len(uploaded_files) > 0 else None,
            image2=uploaded_files[1] if len(uploaded_files) > 1 else None,
            image3=uploaded_files[2] if len(uploaded_files) > 2 else None,
            image4=uploaded_files[3] if len(uploaded_files) > 3 else None,
            image5=uploaded_files[4] if len(uploaded_files) > 4 else None,
            image6=uploaded_files[5] if len(uploaded_files) > 5 else None
        )
        db.session.add(plan)
        db.session.commit()
        flash('Trading plan added successfully!', 'success')
        return redirect(url_for('trading_plan_history'))
    return render_template('add_trading_plan.html', form=form)

@app.route('/edit_trading_plan/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def edit_trading_plan(plan_id):
    plan = TradingPlan.query.get_or_404(plan_id)
    form = TradingPlanForm(obj=plan)
    if form.validate_on_submit():
        # Update the trading plan fields
        plan.market_conditions = form.market_conditions.data
        plan.goals = form.goals.data
        plan.risk_management = form.risk_management.data
        plan.entry_exit_criteria = form.entry_exit_criteria.data
        plan.trade_setup = form.trade_setup.data
        plan.review_notes = form.review_notes.data
        plan.news_events = form.news_events.data
        plan.premarket_routine = form.premarket_routine.data
        plan.timeframe = form.timeframe.data
        plan.market_type = form.market_type.data
        plan.entries = form.entries.data
        plan.stop_loss = form.stop_loss.data
        plan.take_profit = form.take_profit.data

        # Handle newly uploaded images
        for i in range(1, 7):
            uploaded_file = request.files.get(f'image{i}')
            if uploaded_file and uploaded_file.filename != '':
                filename = save_file(uploaded_file)
                setattr(plan, f'image{i}', filename)

        db.session.commit()
        flash('Trading plan updated successfully!', 'success')
        return redirect(url_for('trading_plan_history'))
    return render_template('edit_trading_plan.html', form=form, plan=plan)

def save_file(file):
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

@app.route('/view_trading_plan/<int:plan_id>')
@login_required
def view_trading_plan(plan_id):
    plan = TradingPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        abort(403)
    return render_template('view_trading_plan.html', trading_plan=plan)

@app.route('/trading_plan_history', methods=['GET'])
@login_required
def trading_plan_history():
    plans = TradingPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('trading_plan_history.html', plans=plans)

@app.route('/today_trading_plan')
@login_required
def today_trading_plan():
    today_plan = get_today_trading_plan(current_user.id)
    if today_plan:
        return redirect(url_for('view_trading_plan', plan_id=today_plan.id))
    else:
        flash('No trading plan found for today. Please create a new one.', 'warning')
        return redirect(url_for('add_trading_plan'))

@app.route('/delete_trading_plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_trading_plan(plan_id):
    plan = TradingPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        abort(403)
    db.session.delete(plan)
    db.session.commit()
    flash('Trading plan deleted successfully!', 'success')
    return redirect(url_for('trading_plan_history'))


@app.context_processor
def inject_user_data():
    def get_latest_trading_plan_id(user_id):
        latest_plan = TradingPlan.query.filter_by(user_id=user_id).order_by(TradingPlan.date.desc()).first()
        return latest_plan.id if latest_plan else None

    if current_user.is_authenticated:
        user_data = UserData.query.filter_by(user_id=current_user.id).first()
        return dict(user_data=user_data, current_user=current_user, get_latest_trading_plan_id=get_latest_trading_plan_id)
    return dict(user_data=None, current_user=None, get_latest_trading_plan_id=get_latest_trading_plan_id)
