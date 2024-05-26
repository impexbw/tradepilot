"""Add last_update_date to UserData

Revision ID: bee5fee69b8f
Revises: 18366a2219ca
Create Date: 2024-05-25 12:40:09.180101

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime  # Add this import


# revision identifiers, used by Alembic.
revision = 'bee5fee69b8f'
down_revision = '18366a2219ca'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_update_date', sa.Date(), nullable=False, server_default=str(datetime.utcnow().date())))

    # Manually set the default value for existing rows
    op.execute("UPDATE user_data SET last_update_date = CURDATE() WHERE last_update_date IS NULL")

def downgrade():
    with op.batch_alter_table('user_data', schema=None) as batch_op:
        batch_op.drop_column('last_update_date')

    # ### end Alembic commands ###
