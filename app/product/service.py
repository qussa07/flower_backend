from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from app.orders.models import OrderItems
from ..user.models import User
from fastapi import HTTPException, UploadFile
from .schemas import ProductModels, ProductUpdate
from .models import Product, CompoundProduct
import re
from uuid import UUID
from .storage import (
    commit_tmp,
    save_tmp,
    delete_photo,
    ALLOWED_TYPES,
    ID_RE,
    MAX_SIZE,
    MAX_FILES,
    PRODUCT_DIR,
    photo_path,
    rollback_photos,
    remove_empty_product_dir,
)
from sqlalchemy import String, cast, or_
from app.categories.models import Categories
import pagination
import utils
from uuid import UUID, uuid4
import logging
from sqlalchemy import exists, func, or_

MAX_TOKENS = 8

PHOTO_URL = re.compile(
    r"/files/(?:tmp|category|product/"
    r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})/"
    r"[0-9a-f]{32}\.(?:jpg|png|webp)"
)


class ProductService():
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, form: ProductModels):
        if form.category_id is not None:
            category = self.db.get(Categories, form.category_id)
            if category is None:
                raise HTTPException(404, "Категория не найдена")

        product = Product(
            category_id=form.category_id,
            title=form.title,
            price=form.price,
            description=form.description,
            count=form.count,
            is_show=form.is_show,
            is_show_case=form.is_show_case,
            image_paths=[],
            compounds=[
                CompoundProduct(
                    title=item.title,
                    quantity=item.quantity,
                )
                for item in form.compounds
            ],
        )

        photo_paths = []

        try:
            self.db.add(product)
            self.db.flush()

            # После flush у товара уже есть ID.
            if form.image_paths:
                try:
                    photo_paths = commit_tmp(
                        form.image_paths,
                        product_id=product.id,
                    )
                except FileNotFoundError:
                    raise HTTPException(
                        400,
                        "Фото не найдено. Загрузите его повторно",
                    ) from None

            product.image_paths = photo_paths
            self.db.commit()

        except Exception:
            self.db.rollback()
            rollback_photos(photo_paths)
            raise

        self.db.refresh(product)

        return {"id": product.id, "photos": photo_paths,}

    def get_product(self, id: UUID, public_only: bool = False):
        query = (
            self.db.query(Product)
            .options(selectinload(Product.compounds))
            .filter(Product.id == id)
        )

        query = self._public_filter(query, public_only)
        product = query.first()

        if product is None:
            raise HTTPException(404, "Товар не найден")

        return product

    def _price_filter(self, query, min_price, max_price):
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(422, "Минимальная цена не может превышать максимальную")
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)
        return query

    def _sort_products(self, query, sort):
        ordering = {
            "new": Product.created_at.desc(),
            "old": Product.created_at.asc(),
            "cheap": Product.price.asc(),
            "expensive": Product.price.desc(),
            "asc": Product.title.asc(),
            "desc": Product.title.desc(),
            "price_asc": Product.price.asc(),
            "price_desc": Product.price.desc(),
        }
        return query.order_by(ordering[sort], Product.id)

    def get_products(self, page: int, perPage: int, search=None, 
                     min_price=None, max_price=None, category_ids: list[UUID] | None = None, sort=None, 
                     is_ready: bool = False, is_not_show: bool = False, public_only: bool = False):
        tokens = (search or "").split()[:MAX_TOKENS]
        if tokens:
            result = self._run(tokens=tokens, fuzzy=False, per_page=perPage, page=page, min_price=min_price, max_price=max_price, sort=sort, category_ids=category_ids, is_ready=is_ready, is_not_show=is_not_show, public_only=public_only)
            return result
        query = self._price_filter( 
        self.db.query(Product).options(selectinload(Product.compounds)), min_price, max_price)
        query = self._public_filter(query, public_only)
        if is_ready:
            query = query.filter(Product.is_show_case.is_(is_ready))

        if is_not_show:
            query = query.filter(Product.is_show.is_(False))
        if category_ids is not None:
            query = query.filter(Product.category_id.in_(category_ids))
        if sort:
            query = self._sort_products(query, sort)
        else:
            query = query.order_by(Product.created_at.desc(), Product.id)
        return pagination.paginate(query, page, perPage)

    def upload_file(self, photos: list[UploadFile],  redis: Session):
        if len(photos) > MAX_FILES:
            raise HTTPException(400, f"Можно загрузить не больше {MAX_FILES} файлов")

        contents = []
        for photo in photos:
            content = photo.file.read(MAX_SIZE + 1)

            if len(content) > MAX_SIZE:
                raise HTTPException(
                    413, f"{photo.filename}: файл больше 5 МБ"
                )

            actual_type = utils.validate_image(content, photo.filename or "Фото")
            contents.append((content, actual_type))

        ids = []
        for c, t in contents:
            id = save_tmp(c, t)
            ids.append(id)
        return {"upload_ids": ids}

    def _image_is_used(self, image_url: str) -> bool:
        used_by_product = self.db.query(Product.id).filter(
            Product.image_paths.contains([image_url])
        ).first()
        if used_by_product:
            return True

        return self.db.query(Categories.id).filter(
            Categories.image_path == image_url
        ).first() is not None

    def _delete_unused_image(self, image_url: str) -> None:
        if not self._image_is_used(image_url):
            delete_photo(image_url)

    def delete_image(self, image_url: str) -> None:
        if not PHOTO_URL.fullmatch(image_url):
            raise HTTPException(422, "Некорректная ссылка на фото")

        if self._image_is_used(image_url):
            raise HTTPException(409, "Фото ещё используется товаром или категорией")

        try:
            unlink_photo(image_url)
        except ValueError as exc:
            raise HTTPException(422, "Некорректный путь к фото") from exc
        except OSError as exc:
            logging.getLogger(__name__).exception(
                "Не удалось удалить фото %s", image_url
            )
            raise HTTPException(500, "Не удалось удалить фото") from exc

    def _token_condition(self, token: str, fuzzy: bool):
        """Слово должно найтись где-то: в букете или в его составе."""
        if fuzzy:
            # триграммы: опечатки и часть слова
            in_product = Product.title.op("%")(token)
            in_compound = exists().where(
                CompoundProduct.product_id == Product.id,
                CompoundProduct.title.op("%")(token),
            )
        else:
            # полнотекстовый поиск с морфологией (роза = розы = роз)
            tsq = func.plainto_tsquery("russian", token)
            in_product = Product.search.op("@@")(tsq)
            in_compound = exists().where(
                CompoundProduct.product_id == Product.id,
                CompoundProduct.search.op("@@")(tsq),
            )

        conds = [in_product, in_compound]

        # число может быть количеством компонента (сравниваем точно)
        if token.isdigit() and len(token) <= 6:
            conds.append(
                exists().where(
                    CompoundProduct.product_id == Product.id,
                    CompoundProduct.quantity == int(token),
                )
            )
        return or_(*conds)

    def _run(self, tokens, fuzzy, per_page, page, min_price=None, max_price=None, category_ids=None, sort=None, is_ready: bool = False, is_not_show: bool = False, public_only: bool = False):
        query = self._price_filter(self.db.query(Product).options(selectinload(Product.compounds)), min_price, max_price)
        query = self._public_filter(query, public_only)
        

        if is_ready == True:
            query = query.filter(Product.is_show_case.is_(is_ready))

        if is_not_show == True:
            query = query.filter(Product.is_show.is_(False)) 

        if category_ids is not None:
            query = query.filter(Product.category_id.in_(category_ids))
        for tok in tokens:
            query = query.filter(self._token_condition(tok, fuzzy))

        if sort:
            query = self._sort_products(query, sort)
        elif not fuzzy:
            # ранжирование: совпадения в названии весят больше, чем в описании
            rank = func.ts_rank(
                Product.search, func.plainto_tsquery("russian", " ".join(tokens))
            )
            query = query.order_by(rank.desc(), Product.created_at.desc(), Product.id)
        else:
            query = query.order_by(
                func.similarity(Product.title, " ".join(tokens)).desc(), Product.id
            )

        return pagination.paginate(query, page, per_page)


    def _public_filter(self, query, public_only: bool):
        if public_only:
            query = query.filter(
                Product.is_show.is_(True),
                # Product.count > Product.reserved_count,
            )
        return query

    def search(self, params, public_only: bool = False):
        tokens = (params.string or "").split()[:MAX_TOKENS]
        if not tokens:
            return {
                "data": [],
                "meta": {
            "perPage": params.per_page,
            "currentPage": params.page,
            "lastPage": 1,
            "total": 0,
            "isNext": False,
            "isPrev": params.page > 1,},
            }

        options = {
            "tokens": tokens,
            "per_page": params.per_page,
            "page": params.page,
            "min_price": params.min_price,
            "max_price": params.max_price,
            "sort": params.sort,
            "public_only": public_only,
        }

        result = self._run(fuzzy=False, **options)
        if result["meta"]["total"] > 0:
            return result

        return self._run(fuzzy=True, **options)

    
    def update_product(self, uuid: UUID, form: ProductUpdate):
        product = self.get_product(uuid)

        if form.category_id is not None:
            category = self.db.get(Categories, form.category_id)
            if category is None:
                raise HTTPException(404, "Категория не найдена")

        requested_images = form.image_paths
        replace_images = requested_images is not None
        old_images = list(product.image_paths or [])
        images = old_images.copy()
        new_photo_paths = []

        try:
            if requested_images is not None:
                upload_ids = []
                for value in requested_images:
                    if value in old_images:
                        continue
                    if not ID_RE.fullmatch(value):
                        raise HTTPException(
                            400, "Фото не принадлежит товару или ID загрузки неверный"
                        )
                    upload_ids.append(value)

                if upload_ids:
                    try:
                        new_photo_paths = commit_tmp(upload_ids, product_id=product.id)
                    except FileNotFoundError:
                        raise HTTPException(
                            400, "Фото не найдено. Загрузите его повторно"
                        ) from None

                uploaded = dict(zip(upload_ids, new_photo_paths))
                images = [uploaded.get(value, value) for value in requested_images]

            """if form.count < product.reserved_count:
                raise HTTPException(409, f"Остаток не может быть меньше резерва: {product.reserved_count}")"""

            product.image_paths = images
            product.category_id = form.category_id
            product.title = form.title
            product.price = form.price
            product.description = form.description
            product.count = form.count
            product.is_show = form.is_show and form.count > 0
            product.is_show_case = form.is_show_case

            product.compounds = [
                CompoundProduct(title=item.title, quantity=item.quantity)
                for item in form.compounds
            ]

            self.db.commit()

        except Exception:
            self.db.rollback()

            rollback_photos(new_photo_paths)

            raise

        self.db.refresh(product)
        if replace_images:
            removed_images = set(old_images) - set(product.image_paths or [])

            for image_url in removed_images:
                self._delete_unused_image(image_url)

        return product

    def delete_product(self, product_id: UUID):
        product = self.get_product(product_id)
        if self.db.query(OrderItems.id).filter(OrderItems.product_id == product_id).first():
            raise HTTPException(409, "Товар входит в заказ")

        # Keep files referenced by another product or category.
        photos_to_delete = []
        for photo in product.image_paths or []:
            try:
                path = photo_path(photo)
            except ValueError:
                continue
            used_by_product = self.db.query(Product.id).filter(
                Product.id != product_id, Product.image_paths.contains([photo])
            ).first()
            used_by_category = self.db.query(Categories.id).filter(Categories.image_path == photo).first()
            if not used_by_product and not used_by_category:
                photos_to_delete.append(path)

        try:
            self.db.delete(product)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23503" or getattr(exc.orig, "pgcode", None) == "23503":
                raise HTTPException(409, "На товар ссылается другая запись") from exc
            raise
        except Exception:
            self.db.rollback()
            raise
        for path in photos_to_delete:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logging.getLogger(__name__).exception("Could not delete product photo: %s", path)

        remove_empty_product_dir(PRODUCT_DIR / str(product_id))

        