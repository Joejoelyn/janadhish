import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_db
from ..models import Product
from ..schemas import AIChatRequest
from ..services.groq_service import get_groq_reply

router = APIRouter()


@router.post('/api/ai/chat')
def ai_chat(payload: AIChatRequest, db: Session = Depends(get_db)):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail='Please enter a question for the shopping assistant.')

    products = db.query(Product).filter(Product.is_active == True).all()
    product_summary = '\n'.join(
        [
            f"- {product.name}: {product.short_description or product.description or 'No summary'} | INR {product.price} | stock {product.stock_quantity} | sizes {product.sizes or 'N/A'} | colors {product.colors or 'N/A'}"
            for product in products[:8]
        ]
    )

    prompt = f"""
You are a premium fashion shopping assistant for JANADHISH. Use only the product information provided below.

Product catalog:
{product_summary}

User question: {payload.message}

Rules:
- Never invent prices, products, stock, or policies.
- If information is missing, say so clearly.
- Keep responses friendly and elegant.
- Answer based on real catalog information.
- Do not claim live payment or shipping guarantees beyond what is in the store information.
"""

    try:
        answer = get_groq_reply(prompt)
        return {'response': answer}
    except Exception as exc:
        raise HTTPException(status_code=503, detail='AI assistant is temporarily unavailable. Please try again later.') from exc
