from fastapi import APIRouter, Depends, HTTPException, UploadFile, Query, File
from sqlalchemy.orm import Session
from database import getdb, get_redis
from .service import ProductService
from .schemas import ProductModels, ProductUpdate
from app.user.models import User
from typing import Annotated, Literal
from decimal import Decimal
from uuid import UUID
from .schemas import ProductSearchParams, ProductSort
import utils



router = APIRouter(prefix="/products", tags=['Products'])


def get_user_service(db: Session = Depends(getdb)):
    return ProductService(db)


@router.post("/", dependencies=[Depends(utils.require_staff)])
def create_product(form: ProductModels, service: ProductService = Depends(get_user_service)):   
    return service.create_product(form)


"""@router.post("/uploads", dependencies=[Depends(utils.require_staff)])
def upload_photo(photo: list[UploadFile] = File(...), redis: Session = Depends(get_redis), service: ProductService = Depends(get_user_service)):
    return service.upload_file(photo, redis)"""

@router.get("")
def get_products(
    page: int = Query(1, ge=1),
    perPage: int = Query(20, ge=1, le=100),
    search: str | None = None,
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    sort: ProductSort | None = None,
    category_ids: str | None = Query(default=None),
    service: ProductService = Depends(get_user_service),
    is_ready: bool = True
):
    try:
        ids = [UUID(x.strip()) for x in category_ids.split(",")] if category_ids else None
    except ValueError:
        raise HTTPException(422, "Некорректный ID категории")
    return service.get_products(page=page, perPage=perPage, search=search, min_price=min_price, max_price=max_price, category_ids=ids, sort=sort, public_only=True, is_ready=is_ready)

@router.get("/{product_id}")
def get_product(product_id: UUID, service: ProductService = Depends(get_user_service)):
   return service.get_product(product_id, public_only=True)

"""@router.delete("/uploads", status_code=204, dependencies=[Depends(utils.require_staff)])
def delete_image(
    image_path: str,
    service: ProductService = Depends(get_user_service),
) -> None:
    service.delete_image(image_path)"""

@router.put("/{product_id}", dependencies=[Depends(utils.require_staff)])
def update_product(product_id: UUID, form: ProductUpdate, service: ProductService = Depends(get_user_service)):
    return service.update_product(product_id, form)

@router.delete("/{product_id}", status_code=204, dependencies=[Depends(utils.require_staff)])
def delete_product(product_id: UUID, service: ProductService = Depends(get_user_service)):
    service.delete_product(product_id)