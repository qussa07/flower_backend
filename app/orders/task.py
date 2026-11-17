from datetime import datetime, timezone
from uuid import UUID
from app.product.models import Product
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.orders.models import Orders
from app.orders.schemas import PaymentStatus


async def expire_order(db: AsyncSession, order_id: UUID) -> str:
    result = await db.execute(
        select(Orders)
        .where(Orders.id == order_id)
        .options(selectinload(Orders.items))
        .with_for_update()
    )
    order = result.scalar_one_or_none()

    if order is None:
        return "not_found"

    if order.payment_status != PaymentStatus.PENDING:
        return "not_pending"

    if order.expireAt is None:
        raise ValueError(f"У заказа {order_id} отсутствует expireAt")

    if datetime.now(timezone.utc) < order.expireAt:
        return "not_expired"

    if order.payment_action == "capture":
        return "capture_in_progress"

    if not order.stock_reserved:
        return "no_reservation"

    quantities = {
        item.product_id: item.quantity
        for item in order.items
    }

    result = await db.execute(
        select(Product)
        .where(Product.id.in_(quantities))
        .order_by(Product.id)
        .with_for_update()
    )
    products = result.scalars().all()

    if len(products) != len(quantities):
        raise RuntimeError(
            f"Не найдены товары зарезервированного заказа {order_id}"
        )

    for product in products:
        quantity = quantities[product.id]

        if product.reserved_count < quantity:
            raise RuntimeError(
                f"Нарушен учёт резерва товара {product.id}"
            )

    for product in products:
        product.reserved_count -= quantities[product.id]

    order.stock_reserved = False
    order.payment_action = "cancel"
    order.payment_status = PaymentStatus.CANCELLED

    return "cancelled"