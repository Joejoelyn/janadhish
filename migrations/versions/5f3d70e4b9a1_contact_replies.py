"""Record customer-visible contact replies and status changes.

Revision ID: 5f3d70e4b9a1
Revises: 4b8f91a2c6d0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f3d70e4b9a1'
down_revision: Union[str, None] = '4b8f91a2c6d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contact_updates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('contact_messages.id'), nullable=False),
        sa.Column('reviewer_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reply', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contact_updates_contact_id', 'contact_updates', ['contact_id'])


def downgrade() -> None:
    op.drop_index('ix_contact_updates_contact_id', table_name='contact_updates')
    op.drop_table('contact_updates')
