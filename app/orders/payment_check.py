import asyncio
from uuid import UUID

from sqlalchemy import select

from database import SessionLocal
from db_async_ import AsyncSessionLocal
from app.orders.models import Orders
from app.orders.services import OrdersService


def _process_payment_sync(payment_id: str) -> dict:
    # Сессия создаётся и закрывается внутри рабочего потока.
    with SessionLocal() as db:
        service = OrdersService(db)
        return service.process_payment(payment_id)


async def check_order_payment(order_id: UUID) -> str:
    async with AsyncSessionLocal() as db:
        payment_id = await db.scalar(
            select(Orders.payment_id)
            .where(Orders.id == order_id)
        )

    # Асинхронная сессия здесь уже закрыта.
    if not payment_id:
        raise RuntimeError(
            f"Для проверки оплаты заказа {order_id} нет payment_id"
        )

    result = await asyncio.to_thread(
        _process_payment_sync,
        payment_id,
    )

    status = result.get("status")

    if status not in {"ok", "succeeded", "canceled"}:
        raise RuntimeError(
            f"Платёж заказа {order_id} ещё не завершён: {status}"
        )

    return status