from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ProductBase(BaseModel):
    sku: str
    name: str
    short_description: str | None = None
    description: str | None = None
    fabric_details: str | None = None
    care_instructions: str | None = None
    price: float
    sale_price: float | None = None
    sizes: str | None = None
    colors: str | None = None
    category_id: int | None = None
    stock_quantity: int = 0
    image_url: str | None = None
    gallery: str | None = None
    is_new_arrival: bool = False
    is_best_seller: bool = False
    is_featured: bool = False
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: int
    category: dict | None = None


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = None
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None = None
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserOut


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    size: str | None = None
    color: str | None = None


class CustomRequestCreate(BaseModel):
    garment_category: str
    fabric_name: str | None = None
    design_name: str | None = None
    measurements: dict[str, Any] = {}
    preferences: dict[str, Any] = {}
    special_instructions: str | None = None
    estimated_price: float = 0


class OrderCreate(BaseModel):
    customer_name: str
    email: EmailStr
    phone: str | None = None
    shipping_address: str
    city: str
    state: str
    postal_code: str
    country: str
    shipping_method: str = 'standard'
    payment_method: str = 'test_mode'
    cart_items: list[dict] = []


class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    subject: str | None = None
    message: str


class AIChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None
