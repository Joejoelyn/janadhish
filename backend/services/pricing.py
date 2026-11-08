from ..models import Product


def product_variant_prices(product: Product) -> tuple[float, float | None]:
    without_pads = product.sale_price if product.sale_price is not None else product.price
    with_pads = product.price if product.sale_price is not None and product.price > without_pads else None
    return float(without_pads), float(with_pads) if with_pads is not None else None
