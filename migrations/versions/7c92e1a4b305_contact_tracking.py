"""Add private contact request tracking.

Revision ID: 7c92e1a4b305
Revises: 1d4296163d4c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7c92e1a4b305'
down_revision: Union[str, None] = '1d4296163d4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('contact_messages') as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), server_default='received', nullable=False))
        batch_op.add_column(sa.Column('public_token', sa.String(length=100), nullable=True))
        batch_op.create_unique_constraint('uq_contact_messages_public_token', ['public_token'])


def downgrade() -> None:
    with op.batch_alter_table('contact_messages') as batch_op:
        batch_op.drop_constraint('uq_contact_messages_public_token', type_='unique')
        batch_op.drop_column('public_token')
        batch_op.drop_column('status')
