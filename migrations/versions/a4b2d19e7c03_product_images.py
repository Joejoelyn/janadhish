"""Store admin-uploaded catalog images in the database."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4b2d19e7c03'
down_revision: Union[str, None] = '5f3d70e4b9a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_images',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_product_images_product_id', 'product_images', ['product_id'])


def downgrade() -> None:
    op.drop_index('ix_product_images_product_id', table_name='product_images')
    op.drop_table('product_images')
