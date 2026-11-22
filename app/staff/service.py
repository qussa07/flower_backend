from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.orders.models import Orders
from app.orders.schemas import PaymentStatus
from app.user.models import User
from app.product.models import Product
from app.product.service import ProductService
from app.staff.models import CompletionStatusEnum


class StaffOrdersService:
    def __init__(self, db: Session):
        self.db = db

    def get_orders(self):
        return (
            self.db.query(Orders)
            .options(selectinload(Orders.items))
            .filter(
                Orders.payment_status != PaymentStatus.CANCELLED,
                Orders.completion_status != CompletionStatusEnum.COMPLETED,
            )
            .order_by(Orders.created_at.asc(), Orders.id.asc())
            .all()
        )

    def complete_order(self, order_id: UUID):
        order = (
            self.db.query(Orders)
            .options(selectinload(Orders.items))
            .filter(Orders.id == order_id)
            .with_for_update()
            .first()
        )
        if order is None:
            raise HTTPException(404, "Заказ не найден")
        if order.payment_status != PaymentStatus.PAID:
            raise HTTPException(409, "Завершить можно только оплаченный заказ")
        if order.completion_status != CompletionStatusEnum.COMPLETED:
            order.completion_status = CompletionStatusEnum.COMPLETED
            self.db.commit()
        return order


    def get_products(self, page: int, perPage: int, search=None, 
                         min_price=None, max_price=None, category_id: list[UUID] | None = None, sort=None, is_ready: bool = False, is_not_show: bool = False):
        return ProductService(self.db).get_products(page=page, perPage=perPage, 
                                                    search=search, min_price=min_price, max_price=max_price, category_id=category_id, sort=sort, is_ready=is_ready, is_not_show=is_not_show)
    def get_product(self, product_id: UUID):
        return ProductService(self.db).get_product(product_id)