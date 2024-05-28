from tradepilot import celery, db, app
from tradepilot.models import UserData
from datetime import datetime

@celery.task
def update_all_users_balance():
    app.logger.info('Updating balance for all users')
    user_data_list = UserData.query.all()
    for user_data in user_data_list:
        try:
            app.logger.info(f'Updating user {user_data.user_id}')
            update_balance_from_equity(user_data)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error updating user {user_data.user_id}: {e}')
    app.logger.info('Finished updating balance for all users')

def update_balance_from_equity(user_data):
    current_date = datetime.now().date()
    if user_data.last_update_date != current_date:
        user_data.balance = user_data.equity
        user_data.last_update_date = current_date
        db.session.commit()
