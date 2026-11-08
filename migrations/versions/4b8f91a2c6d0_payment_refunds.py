"""Record manually completed refunds.

Revision ID: 4b8f91a2c6d0
Revises: 7c92e1a4b305
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4b8f91a2c6d0'
down_revision: Union[str, None] = '7c92e1a4b305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('refunded_amount_paise', sa.Integer(), server_default='0', nullable=False))
    op.create_table(
        'payment_refunds',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('outgoing_reference', sa.String(length=100), nullable=False, unique=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recorded_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('payment_refunds')
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('refunded_amount_paise')
