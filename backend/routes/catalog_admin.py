import logging
import hashlib
from io import BytesIO
from decimal import Decimal
import warnings

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_current_admin_user, get_db
from ..models import Category, Product, ProductAudit, ProductImage, User
from .products import serialize_product

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_IMAGES = 6
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_STORED_BYTES = 2 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


def normalize_options(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        option = value.strip()
        if not option or len(option) > 30 or ',' in option:
            raise ValueError('Each size or color must be 1–30 characters without commas')
        if option.casefold() not in seen:
            result.append(option)
            seen.add(option.casefold())
    return result


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=40, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]+$')
    name: str = Field(..., min_length=2, max_length=200)
    category_id: int = Field(..., gt=0)
    sizes: list[str] = Field(default_factory=list, max_length=20)
    colors: list[str] = Field(default_factory=list, max_length=20)
    short_description: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
    fabric_details: str | None = Field(default=None, max_length=2000)
    care_instructions: str | None = Field(default=None, max_length=2000)
    without_pads_price: Decimal = Field(..., gt=0, le=1000000, decimal_places=2)
    with_pads_price: Decimal | None = Field(default=None, gt=0, le=1000000, decimal_places=2)
    stock_quantity: int = Field(..., ge=0, le=1000000)
    is_new_arrival: bool = False
    is_best_seller: bool = False
    is_featured: bool = False
    is_active: bool = False

    @field_validator('sizes', 'colors')
    @classmethod
    def valid_options(cls, values: list[str]) -> list[str]:
        return normalize_options(values)

    @model_validator(mode='after')
    def valid_product(self) -> 'ProductCreate':
        if len(self.name.strip()) < 2:
            raise ValueError('Product name is required')
        if self.with_pads_price is not None and self.with_pads_price <= self.without_pads_price:
            raise ValueError('With-pads price must be greater than the standard price')
        return self


class ProductEdit(BaseModel):
    sku: str | None = Field(default=None, min_length=3, max_length=40, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]+$')
    category_id: int | None = Field(default=None, gt=0)
    sizes: list[str] | None = Field(default=None, max_length=20)
    colors: list[str] | None = Field(default=None, max_length=20)
    name: str = Field(..., min_length=2, max_length=200)
    short_description: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
    fabric_details: str | None = Field(default=None, max_length=2000)
    care_instructions: str | None = Field(default=None, max_length=2000)
    without_pads_price: Decimal = Field(..., gt=0, le=1000000, decimal_places=2)
    with_pads_price: Decimal | None = Field(default=None, gt=0, le=1000000, decimal_places=2)
    stock_quantity: int = Field(..., ge=0, le=1000000)
    expected_stock_quantity: int = Field(..., ge=0, le=1000000)
    is_new_arrival: bool
    is_best_seller: bool
    is_featured: bool
    is_active: bool

    @field_validator('sizes', 'colors')
    @classmethod
    def valid_options(cls, values: list[str] | None) -> list[str] | None:
        return normalize_options(values) if values is not None else None

    @model_validator(mode='after')
    def valid_product(self) -> 'ProductEdit':
        if len(self.name.strip()) < 2:
            raise ValueError('Product name is required')
        if self.with_pads_price is not None and self.with_pads_price <= self.without_pads_price:
            raise ValueError('With-pads price must be greater than the standard price')
        return self


def audit_snapshot(product: Product) -> dict[str, str | float | int | bool | None]:
    return {
        'sku': product.sku,
        'category_id': product.category_id,
        'sizes': product.sizes,
        'colors': product.colors,
        'image_url': product.image_url,
        'gallery': product.gallery,
        'name': product.name,
        'short_description': product.short_description,
        'description': product.description,
        'fabric_details': product.fabric_details,
        'care_instructions': product.care_instructions,
        'price': product.price,
        'sale_price': product.sale_price,
        'stock_quantity': product.stock_quantity,
        'is_new_arrival': product.is_new_arrival,
        'is_best_seller': product.is_best_seller,
        'is_featured': product.is_featured,
        'is_active': product.is_active,
    }


def encode_product_image(upload: UploadFile) -> bytes:
    raw = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail='Each photo must be 10 MB or smaller')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'} or getattr(source, 'n_frames', 1) != 1:
                    raise HTTPException(status_code=422, detail='Upload a JPEG, PNG, or WebP still photo')
                if source.width * source.height > 20_000_000:
                    raise HTTPException(status_code=422, detail='Photo dimensions are too large')
                source.load()
                image = ImageOps.exif_transpose(source)
                image.thumbnail((1600, 2000), Image.Resampling.LANCZOS)
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                for quality in (84, 70, 55):
                    output = BytesIO()
                    image.save(output, format='WEBP', quality=quality, method=4)
                    if output.tell() <= MAX_STORED_BYTES:
                        return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(status_code=422, detail='Could not read this product photo') from exc
    raise HTTPException(status_code=413, detail='Optimized photo is still too large')


def processed_images(uploads: list[UploadFile]) -> list[bytes]:
    if not 1 <= len(uploads) <= MAX_IMAGES:
        raise HTTPException(status_code=422, detail='Choose 1 to 6 product photos')
    return [encode_product_image(upload) for upload in uploads]


def store_images(db: Session, product_id: int, contents: list[bytes]) -> tuple[list[str], list[int]]:
    urls: list[str] = []
    ids: list[int] = []
    for content in contents:
        image = ProductImage(product_id=product_id, content=content, sha256=hashlib.sha256(content).hexdigest())
        db.add(image)
        db.flush()
        ids.append(image.id)
        urls.append(f'/media/products/{product_id}/{image.id}.webp')
    return urls, ids


@router.post('/api/admin/products', status_code=201)
def create_product(
    details: str = Form(...), images: list[UploadFile] = File(...),
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict[str, object]:
    try:
        payload = ProductCreate.model_validate_json(details)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail='Check the product details and try again') from exc
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=422, detail='Choose an existing collection')
    contents = processed_images(images)
    product = Product(
        sku=payload.sku.upper(), name=payload.name.strip(), category_id=payload.category_id,
        sizes=','.join(payload.sizes) or None, colors=','.join(payload.colors) or None,
        short_description=payload.short_description.strip() if payload.short_description else None,
        description=payload.description.strip() if payload.description else None,
        fabric_details=payload.fabric_details.strip() if payload.fabric_details else None,
        care_instructions=payload.care_instructions.strip() if payload.care_instructions else None,
        price=float(payload.with_pads_price or payload.without_pads_price),
        sale_price=float(payload.without_pads_price) if payload.with_pads_price is not None else None,
        stock_quantity=payload.stock_quantity, is_new_arrival=payload.is_new_arrival,
        is_best_seller=payload.is_best_seller, is_featured=payload.is_featured,
        is_active=payload.is_active,
    )
    try:
        db.add(product)
        db.flush()
        urls, _ = store_images(db, product.id, contents)
        product.image_url = urls[0]
        product.gallery = ','.join(urls)
        db.add(ProductAudit(product_id=product.id, editor_user_id=admin.id,
                            before={}, after=audit_snapshot(product)))
        db.commit()
        db.refresh(product)
        return serialize_product(product)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='This SKU is already in the catalog') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not create product')
        raise HTTPException(status_code=503, detail='Could not add product') from exc


@router.post('/api/admin/products/{product_id}/images')
def replace_product_images(
    product_id: int, expected_image_url: str = Form(...), images: list[UploadFile] = File(...),
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found')
    contents = processed_images(images)
    before = audit_snapshot(product)
    try:
        changed = db.execute(update(Product).where(
            Product.id == product_id, Product.image_url == (expected_image_url or None),
        ).values(image_url=None))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Product photos changed. Refresh before saving.')
        db.refresh(product)
        urls, new_ids = store_images(db, product_id, contents)
        product.image_url = urls[0]
        product.gallery = ','.join(urls)
        db.execute(delete(ProductImage).where(
            ProductImage.product_id == product_id, ProductImage.id.not_in(new_ids),
        ))
        db.add(ProductAudit(product_id=product_id, editor_user_id=admin.id,
                            before=before, after=audit_snapshot(product)))
        db.commit()
        db.refresh(product)
        return serialize_product(product)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not replace images for product %s', product_id)
        raise HTTPException(status_code=503, detail='Could not replace product photos') from exc


@router.get('/api/admin/products')
def list_admin_products(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> list[dict[str, object]]:
    del admin
    return [serialize_product(product) for product in db.query(Product).order_by(Product.name).all()]


@router.put('/api/admin/products/{product_id}')
def edit_product(product_id: int, payload: ProductEdit, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found')
    if payload.category_id is not None and db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=422, detail='Choose an existing collection')
    before = audit_snapshot(product)
    try:
        changed = db.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock_quantity == payload.expected_stock_quantity)
            .values(stock_quantity=payload.stock_quantity)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Available stock changed. Refresh products before saving.')
        db.refresh(product)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not reserve catalog stock update for product %s', product_id)
        raise HTTPException(status_code=503, detail='Could not save product') from exc
    if payload.sku is not None:
        product.sku = payload.sku.upper()
    if payload.category_id is not None:
        product.category_id = payload.category_id
    if payload.sizes is not None:
        product.sizes = ','.join(payload.sizes) or None
    if payload.colors is not None:
        product.colors = ','.join(payload.colors) or None
    product.name = payload.name.strip()
    product.short_description = payload.short_description.strip() if payload.short_description else None
    product.description = payload.description.strip() if payload.description else None
    product.fabric_details = payload.fabric_details.strip() if payload.fabric_details else None
    product.care_instructions = payload.care_instructions.strip() if payload.care_instructions else None
    product.price = float(payload.with_pads_price or payload.without_pads_price)
    product.sale_price = float(payload.without_pads_price) if payload.with_pads_price is not None else None
    product.stock_quantity = payload.stock_quantity
    product.is_new_arrival = payload.is_new_arrival
    product.is_best_seller = payload.is_best_seller
    product.is_featured = payload.is_featured
    product.is_active = payload.is_active
    after = audit_snapshot(product)
    try:
        if before != after:
            db.add(ProductAudit(product_id=product.id, editor_user_id=admin.id, before=before, after=after))
        db.commit()
        db.refresh(product)
        return serialize_product(product)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='This SKU is already in the catalog') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not update product %s', product_id)
        raise HTTPException(status_code=503, detail='Could not save product') from exc


@router.get('/api/admin/products/{product_id}/history')
def product_history(product_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> list[dict[str, object]]:
    del admin
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail='Product not found')
    rows = db.query(ProductAudit).filter_by(product_id=product_id).order_by(ProductAudit.created_at.desc()).limit(20).all()
    return [{
        'id': row.id, 'editor_user_id': row.editor_user_id, 'before': row.before,
        'after': row.after, 'created_at': row.created_at.isoformat(),
    } for row in rows]
