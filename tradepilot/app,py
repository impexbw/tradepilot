from tradepilot import app, db
from flask_login import current_user
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from datetime import datetime
from tradepilot.models import UserData

def reset_equity():
    today = datetime.utcnow().date()
    users = UserData.query.all()
    for user in users:
        if user.last_update_date < today:
            user.reset_equity()

scheduler = BackgroundScheduler()
scheduler.add_job(func=reset_equity, trigger="cron", hour=23, minute=59)  # Adjust the time as needed

@app.before_first_request
def initialize_scheduler():
    if not scheduler.running:
        scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())
