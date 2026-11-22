import shutil
import logging
from uuid import UUID
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.product.models import Product
from app.product.service import ProductService
from app.product.storage import (
    commit_tmp,
    photo_path,
    rollback_photos,
    remove_empty_product_dir,
)
from .models import Categories
from .schemas import CategoryCreate, CategoryUpdate, CategorySort

import pagination


class CategoriesService:
    def __init__(self, db: Session):
        self.db = db

    def upload_file(self, photos: list[UploadFile], redis):
        if len(photos) != 1:
            raise HTTPException(400, "Загрузите ровно одно изображение")
        return ProductService(self.db).upload_file(photos, redis)

    def create_category(self, form: CategoryCreate):
        image_path = None
        if form.image_path:
            try:
                image_path = commit_tmp([form.image_path])[0]
            except FileNotFoundError:
                raise HTTPException(400, "Фото не найдено. Загрузите его повторно")
        category = Categories(title=form.title, image_url=image_path)
        try:
            self.db.add(category)
            self.db.commit()
        except Exception:
            self.db.rollback()
            if image_path:
                rollback_photos([image_path])
            raise
        self.db.refresh(category)
        return category

    def get_categories(self, page: int, perPage: int, search: str = "", sort: CategorySort = "new"):
        ordering = {
        "asc": Categories.title.asc(),
        "desc": Categories.title.desc(),
        "new": Categories.created_at.desc(),
        "old": Categories.created_at.asc(),
        }
        query = (
    self.db.query(
        Categories.id,
        Categories.title,
        Categories.image_url.label("image_path"),
        func.count(Product.id).label("count_products"),).outerjoin(Product, Product.category_id
                                                                    == Categories.id))

        if search:
            query = query.filter(
                Categories.title.ilike(f"%{search}%")
            )

        query = query.group_by(
                        Categories.id,
                        Categories.title,
                        Categories.image_url,).order_by(ordering[sort], Categories.id)

        return pagination.paginate(query, page, perPage)
        
    def get_category(self, category_id: UUID):
        category = self.db.get(Categories, category_id)
        if category is None:
            raise HTTPException(404, "Категория не найдена")
        return category

    def _delete_unused_image(self, image_url: str | None):
        if not image_url:
            return
        try:
            path = photo_path(image_url)
        except ValueError:
            return
        if self.db.query(Categories.id).filter(Categories.image_url == image_url).first():
            return
        if self.db.query(Product.id).filter(Product.image_paths.contains([image_url])).first():
            return
        try:
            path.unlink(missing_ok=True)
            remove_empty_product_dir(path.parent)
        except OSError:
            logging.getLogger(__name__).exception(
                "Could not delete category photo: %s",
                path,
            )

    def update_category(self, category_id: UUID, form: CategoryUpdate):
        category = self.get_category(category_id)
        fields = form.model_fields_set
        if "title" in fields and form.title is None:
            raise HTTPException(422, "Укажите название категории")
        
        old_image = category.image_url
        new_photo = None
        if form.image_path is not None:
            try:
                new_photo = commit_tmp([form.image_path])[0]
            except FileNotFoundError:
                raise HTTPException(400, "Фото не найдено. Загрузите его повторно")

        if "title" in fields:
            category.title = form.title
        if new_photo is not None:
            category.image_url = new_photo

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            if new_photo:
                rollback_photos([new_photo])
            raise
        self.db.refresh(category)
        if old_image != category.image_url:
            self._delete_unused_image(old_image)
        return category

    def delete_category(self, category_id: UUID):
        category = self.get_category(category_id)
        if self.db.query(Product.id).filter(Product.category_id == category_id).first():
            raise HTTPException(409, "В категории есть товары")
        old_image = category.image_url
        try:
            self.db.delete(category)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23503" or getattr(exc.orig, "pgcode", None) == "23503":
                raise HTTPException(409, "На категорию ссылается другая запись") from exc
            raise
        except Exception:
            self.db.rollback()
            raise
        self._delete_unused_image(old_image)