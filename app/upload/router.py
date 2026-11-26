from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.categories.service import CategoriesService
from app.product.service import ProductService
from database import getdb
from utils import require_staff

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(require_staff)],
)


@router.post("")
def upload_photo(
    photos: list[UploadFile] = File(...),
    db: Session = Depends(getdb),
):
    return ProductService(db).upload_file(photos)


@router.delete("", status_code=204)
def delete_image(image_path: str, db: Session = Depends(getdb)) -> None:
    ProductService(db).delete_image(image_path)