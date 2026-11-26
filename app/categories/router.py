from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session
from uuid import UUID
from utils import require_staff
from fastapi import Query
from .schemas import CategorySort

from database import getdb, get_redis
from .schemas import CategoryCreate, CategoryResponse, CategoryUpdate
from .service import CategoriesService

import pagination


router = APIRouter(prefix="/categories", tags=["categories"])


def get_categories_service(db: Session = Depends(getdb)):
    return CategoriesService(db)


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_staff)])
def create_category(form: CategoryCreate, service: CategoriesService = Depends(get_categories_service)):
    return service.create_category(form)
"""
@router.post("/uploads", dependencies=[Depends(require_staff)])
def upload_photo(photo: list[UploadFile] = File(...), redis = Depends(get_redis), service: CategoriesService = Depends(get_categories_service)):
    return service.upload_file(photo, redis)"""

@router.get("/", response_model=pagination.Page[CategoryResponse])
def get_categories(
    page: int = Query(1, ge=1),
    perPage: int = Query(20, ge=1, le=100),
    search: str = "",
    sort: CategorySort = "new",
    service: CategoriesService = Depends(get_categories_service),
):
    return service.get_categories(
        page=page,
        perPage=perPage,
        search=search,
        sort=sort,
    )

@router.get("/{category_id}")
def get_category(category_id: UUID, service: CategoriesService = Depends(get_categories_service)):
    return service.get_category(category_id)

"""@router.delete("/uploads", status_code=204, dependencies=[Depends(require_staff)])
def delete_image(
    image_path: str,
    service: CategoriesService = Depends(get_categories_service),
) -> None:
    service.delete_image(image_path)
"""

@router.put("/{category_id}", dependencies=[Depends(require_staff)])
def update_category(category_id: UUID, form: CategoryUpdate, service: CategoriesService = Depends(get_categories_service)):
    return service.update_category(category_id, form)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_staff)])
def delete_category(category_id: UUID, service: CategoriesService = Depends(get_categories_service)):
    service.delete_category(category_id)