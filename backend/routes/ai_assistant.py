import logging
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_db
from ..models import Product
from ..schemas import AIChatRequest
from ..services.groq_service import get_groq_reply
from ..services.pricing import product_variant_prices

router = APIRouter()
logger = logging.getLogger(__name__)
POLICY_TERMS = {'ship', 'shipping', 'delivery', 'return', 'returns', 'refund', 'refunds',
                'exchange', 'exchanges', 'payment', 'pay', 'upi', 'cash', 'cod'}


def question_terms(message: str) -> set[str]:
    return set(re.findall(r'[a-z]+', message.casefold()))


def product_summary(message: str, products: list[Product]) -> str:
    terms = {term for term in question_terms(message) if len(term) >= 3} - {
        'the', 'and', 'for', 'with', 'what', 'have', 'want', 'show', 'looking', 'under', 'please',
    }

    def relevance(product: Product) -> int:
        name = product.name.casefold()
        details = f'{product.short_description or ""} {product.fabric_details or ""} {product.category.name if product.category else ""}'.casefold()
        exact_name = 10 if product.name.casefold() in message.casefold() else 0
        return exact_name + sum(3 * (term in name) + (term in details) for term in terms)

    available = [product for product in products if product.stock_quantity > 0]
    selected = sorted(available, key=relevance, reverse=True)[:8]
    lines = []
    for product in selected:
        standard, with_pads = product_variant_prices(product)
        prices = f'standard INR {standard:g}'
        if with_pads is not None:
            prices += f', with pads INR {with_pads:g}'
        lines.append(
            f'- {product.name}: {product.short_description or product.description or "No summary"} | '
            f'{prices} | stock {product.stock_quantity} | sizes {product.sizes or "N/A"} | '
            f'colors {product.colors or "N/A"}'
        )
    return '\n'.join(lines)


def catalog_reply(message: str, products: list[Product]) -> str:
    words = question_terms(message)
    policy_answers = []
    if words & {'ship', 'shipping', 'delivery'}:
        policy_answers.append('Standard shipping is ₹250 below ₹3,000 and complimentary from ₹3,000. Express availability must be confirmed with our team.')
    if words & {'return', 'returns', 'refund', 'refunds', 'exchange', 'exchanges'}:
        policy_answers.append('Our return and refund policy is being finalised. Please contact the JANADHISH team before ordering if you need specific terms.')
    if words & {'payment', 'pay', 'upi', 'cash', 'cod'}:
        policy_answers.append('Checkout currently uses the JANADHISH UPI QR. Your payment is confirmed only after our team checks the transaction against the receiving account.')
    if policy_answers:
        return ' '.join(policy_answers)
    terms = {term for term in words if len(term) >= 3} - {'the', 'and', 'for', 'with', 'what', 'have', 'want', 'show', 'looking', 'under', 'please'}
    matches = []
    for product in products:
        if product.stock_quantity < 1:
            continue
        haystack = f'{product.name} {product.short_description or ""} {product.fabric_details or ""} {product.category.name if product.category else ""}'.lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            matches.append((score, product))
    matches.sort(key=lambda item: item[0], reverse=True)
    if not matches:
        return 'I can help you explore our kurtis, tops, kurta sets, and farshi sets. Try asking for a fabric, colour, or style, or browse the collection.'
    suggestions = ', '.join(f'{product.name} (₹{int(product.sale_price or product.price):,})' for _, product in matches[:3])
    return f'You might like: {suggestions}. Open the collection to see sizes, colours, and current availability.'


@router.post('/api/ai/chat')
def ai_chat(payload: AIChatRequest, db: Session = Depends(get_db)):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail='Please enter a question for the shopping assistant.')

    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    if question_terms(payload.message) & POLICY_TERMS:
        return {'response': catalog_reply(payload.message, products)}
    summary = product_summary(payload.message, products)
    if not summary:
        return {'response': 'No pieces are currently available. Please check the collection again later or contact the JANADHISH team.'}

    prompt = f"""
You are a premium fashion shopping assistant for JANADHISH. Use only the product information provided below.

Product catalog:
{summary}

User question: {payload.message}

Rules:
- Never invent prices, products, stock, or policies.
- If information is missing, say so clearly.
- Keep responses friendly and elegant.
- Answer based on real catalog information.
- Do not claim live payment or shipping guarantees beyond what is in the store information.
"""

    if payload.allow_external_ai and os.getenv('GROQ_API_KEY'):
        try:
            return {'response': get_groq_reply(prompt)}
        except Exception:
            logger.exception('AI assistant unavailable; using catalog response')
    return {'response': catalog_reply(payload.message, products)}
