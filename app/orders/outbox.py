import asyncio
import logging
from datetime import datetime, timezone
from math import ceil

from bullmq import Queue
from sqlalchemy import select

from db_async_ import AsyncSessionLocal
from app.orders.models import OrderExpirationOutbox


logger = logging.getLogger(__name__)


async def publish_one(queue: Queue) -> bool:
    async with AsyncSessionLocal.begin() as db:
        record = await db.scalar(
            select(OrderExpirationOutbox)
            .order_by(OrderExpirationOutbox.order_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        if record is None:
            return False

        order_id = str(record.order_id)

        delay_ms = max(
            0,
            ceil(
                (record.run_at - datetime.now(timezone.utc))
                .total_seconds() * 1000
            ),
        )

        await asyncio.wait_for(
            queue.add(
                "expire-order",
                {"order_id": order_id},
                {
                    "jobId": f"expire-{order_id}",
                    "delay": delay_ms,
                    "attempts": 5,
                    "backoff": {
                        "type": "exponential",
                        "delay": 2000,
                    },
                    "removeOnComplete": 1000,
                    "removeOnFail": False,
                },
            ),
            timeout=5,
        )

        await db.delete(record)

    logger.info("Задача отправлена в Redis: заказ %s", order_id)
    return True


async def publish_outbox(
    queue: Queue,
    stop_event: asyncio.Event,
):
    while not stop_event.is_set():
        try:
            if await publish_one(queue):
                continue
        except Exception:
            logger.exception("Не удалось отправить сообщение из очереди исходящих событий")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=5,
            )
        except TimeoutError:
            pass