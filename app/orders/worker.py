import asyncio
import logging
import os
import signal
import sys
from uuid import UUID
from app.categories.models import Categories
from bullmq import Queue, Worker
from contextlib import suppress

from app.orders.outbox import publish_outbox

from database import engine as sync_engine
from db_async_ import AsyncSessionLocal, async_engine
from app.orders.task import expire_order
from app.user.models import User


logger = logging.getLogger(__name__)


async def process(job, job_token):
    if job.name != "expire-order":
        raise ValueError(f"Неизвестная задача: {job.name}")

    order_id = UUID(job.data["order_id"])

    async with AsyncSessionLocal.begin() as db:
        outcome = await expire_order(db, order_id)

    if outcome == "not_expired":
        raise RuntimeError(
            f"Задача заказа {order_id} запущена раньше срока"
        )

    if outcome == "no_reservation":
        raise RuntimeError(
            f"Заказ {order_id} ожидает оплаты, но резерв отсутствует"
        )

    logger.info("Заказ %s: %s", order_id, outcome)
    return {"status": outcome}

def on_error(error, *args):
    logger.error("Ошибка worker: %s", error)


def on_failed(job, error):
    logger.error("Ошибка задачи %s: %s", job.id, error)


async def main():
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(signum, frame):
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    redis_url = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379",
    )

    queue = Queue(
        "order-expiration",
        {"connection": redis_url},
    )

    worker = Worker(
        "order-expiration",
        process,
        {
            "connection": redis_url,
            "concurrency": 1,
        },
    )

    worker.on("error", on_error)
    worker.on("failed", on_failed)

    publisher_task = asyncio.create_task(
        publish_outbox(queue, stop_event)
    )

    try:
        logger.info("Worker и отправитель outbox запущены.")
        await stop_event.wait()
    finally:
        logger.info("Останавливаем отправитель и worker...")

        publisher_task.cancel()

        with suppress(asyncio.CancelledError):
            await publisher_task

        try:
            await worker.close()
        finally:
            try:
                await queue.close()
            finally:
                await async_engine.dispose()
                await asyncio.to_thread(sync_engine.dispose)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main())