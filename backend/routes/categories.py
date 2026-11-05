from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_db
from ..models import Category

router = APIRouter()


@router.get('/api/categories')
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return [
        {
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
        }
        for category in categories
    ]
