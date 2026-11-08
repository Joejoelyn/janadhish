from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


INDIAN_REGIONS = frozenset({
    'Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam',
    'Bihar', 'Chandigarh', 'Chhattisgarh', 'Dadra and Nagar Haveli and Daman and Diu',
    'Delhi', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jammu and Kashmir',
    'Jharkhand', 'Karnataka', 'Kerala', 'Ladakh', 'Lakshadweep', 'Madhya Pradesh',
    'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha',
    'Puducherry', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
    'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
})


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
    phone: str | None = Field(default=None, max_length=50)
    password: str = Field(..., min_length=8)

    @field_validator('full_name', 'phone', mode='before')
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


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
    product_id: int = Field(..., gt=0)
    quantity: int = Field(default=1, ge=1, le=100)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)


class CustomRequestCreate(BaseModel):
    garment_category: Literal['Saree', 'Kurta', 'Anarkali', 'Fusion Set', 'Gown']
    fabric_name: str = Field(..., min_length=1, max_length=100)
    design_name: str = Field(..., min_length=1, max_length=100)
    contact_name: str | None = Field(default=None, min_length=2, max_length=150)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    measurements: dict[str, float] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    special_instructions: str | None = Field(default=None, max_length=1000)

    @field_validator('fabric_name', 'design_name', 'contact_name', 'contact_phone', 'special_instructions', mode='before')
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1, le=100)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    with_pads: bool = False
    customization_details: str | dict[str, Any] | None = None


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    shipping_address: str = Field(..., min_length=5, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., pattern=r'^[1-9][0-9]{5}$')
    country: Literal['India']
    shipping_method: Literal['standard', 'express'] = 'standard'
    payment_method: Literal['upi_qr'] = 'upi_qr'
    checkout_key: str = Field(..., min_length=16, max_length=100)
    cart_items: list[OrderItemCreate] = Field(..., min_length=1)

    @field_validator('customer_name', 'phone', 'shipping_address', 'city', 'state', mode='before')
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator('state')
    @classmethod
    def valid_state(cls, value: str) -> str:
        if value not in INDIAN_REGIONS:
            raise ValueError('Choose a valid Indian state or union territory')
        return value


class CheckoutRecovery(BaseModel):
    checkout_key: str = Field(..., min_length=16, max_length=100)


class ContactCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(..., min_length=5, max_length=5000)

    @field_validator('name', 'phone', 'subject', 'message', mode='before')
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    context: dict[str, Any] | None = None
    allow_external_ai: bool = False

    @field_validator('message', mode='before')
    @classmethod
    def trim_message(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value
