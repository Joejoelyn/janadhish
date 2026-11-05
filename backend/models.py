from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Category(Base):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    products: Mapped[list['Product']] = relationship(back_populates='category')


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fabric_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    care_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    sale_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sizes: Mapped[str | None] = mapped_column(Text, nullable=True)
    colors: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('categories.id'), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gallery: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_new_arrival: Mapped[bool] = mapped_column(Boolean, default=False)
    is_best_seller: Mapped[bool] = mapped_column(Boolean, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped[Category | None] = relationship(back_populates='products')
    cart_items: Mapped[list['CartItem']] = relationship(back_populates='product')
    order_items: Mapped[list['OrderItem']] = relationship(back_populates='product')


class Fabric(Base):
    __tablename__ = 'fabrics'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_price: Mapped[float] = mapped_column(Float, default=0)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Design(Base):
    __tablename__ = 'designs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[list['Order']] = relationship(back_populates='user')
    cart_items: Mapped[list['CartItem']] = relationship(back_populates='user')
    custom_requests: Mapped[list['CustomRequest']] = relationship(back_populates='user')


class CartItem(Base):
    __tablename__ = 'cart_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    custom_request_id: Mapped[int | None] = mapped_column(ForeignKey('custom_requests.id'), nullable=True)

    user: Mapped[User | None] = relationship(back_populates='cart_items')
    product: Mapped[Product] = relationship(back_populates='cart_items')
    custom_request: Mapped['CustomRequest | None'] = relationship(back_populates='cart_items')


class CustomRequest(Base):
    __tablename__ = 'custom_requests'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    garment_category: Mapped[str] = mapped_column(String(100), nullable=False)
    fabric_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    design_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    measurements: Mapped[dict] = mapped_column(JSON, default={})
    preferences: Mapped[dict] = mapped_column(JSON, default={})
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_price: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User | None] = relationship(back_populates='custom_requests')
    cart_items: Mapped[list['CartItem']] = relationship(back_populates='custom_request')


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipping_address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    shipping_method: Mapped[str] = mapped_column(String(50), default='standard')
    payment_method: Mapped[str] = mapped_column(String(50), default='test_mode')
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    shipping_fee: Mapped[float] = mapped_column(Float, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User | None] = relationship(back_populates='orders')
    items: Mapped[list['OrderItem']] = relationship(back_populates='order')


class OrderItem(Base):
    __tablename__ = 'order_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey('products.id'), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    customization_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates='items')
    product: Mapped[Product | None] = relationship(back_populates='order_items')


class ContactMessage(Base):
    __tablename__ = 'contact_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
