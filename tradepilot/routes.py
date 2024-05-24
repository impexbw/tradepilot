from flask import render_template, url_for, flash, redirect, request
from tradepilot import app, db, bcrypt
from tradepilot.forms import RegistrationForm, LoginForm, UserDataForm, TradeForm
from tradepilot.models import User, UserData, Trade
from flask_login import login_user, current_user, logout_user, login_required

@app.route('/')
@app.route('/dashboard')
@login_required
def index():
    user_data = UserData.query.filter_by(user_id=current_user.id).first()
    last_ten_trades = Trade.query.filter_by(user_id=current_user.id).order_by(Trade.open_time.desc()).limit(10).all()
    return render_template('index.html', user_data=user_data, last_ten_trades=last_ten_trades)

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

@app.route('/add_trade', methods=['GET', 'POST'])
@login_required
def add_trade():
    form = TradeForm()
    if form.validate_on_submit():
        trade = Trade(
            user_id=current_user.id,
            ticket=form.ticket.data,
            open_time=form.open_time.data,
            trade_type=form.trade_type.data,
            size=form.size.data,
            item=form.item.data,
            price=form.price.data,
            s_l=form.s_l.data,
            t_p=form.t_p.data,
            close_time=form.close_time.data,
            close_price=form.close_price.data,
            comm=form.comm.data,
            taxes=form.taxes.data,
            swap=form.swap.data,
            profit=form.profit.data
        )
        db.session.add(trade)
        db.session.commit()
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
        db.session.commit()
        flash('Your trade has been updated!', 'success')
        return redirect(url_for('trades'))
    
    return render_template('edit_trade.html', title='Edit Trade', form=form, trade=trade)

@app.route('/trade/delete/<int:trade_id>', methods=['POST'])
@login_required
def delete_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if trade.user_id != current_user.id:
        abort(403)
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
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        if start_date and end_date:
            # Filter trades by date range
            user_trades = Trade.query.filter_by(user_id=current_user.id).filter(
                Trade.open_time >= start_date,
                Trade.open_time <= end_date
            ).all()
        else:
            # No date range provided, show all trades
            user_trades = Trade.query.filter_by(user_id=current_user.id).all()
    else:
        # Show all trades for the user
        user_trades = Trade.query.filter_by(user_id=current_user.id).all()
    return render_template('trades.html', trades=user_trades, user_data=user_data)

@app.context_processor
def inject_user_data():
    if current_user.is_authenticated:
        user_data = UserData.query.filter_by(user_id=current_user.id).first()
        return dict(user_data=user_data)
    return dict(user_data=None)
