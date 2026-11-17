import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

import utils
from app.product.storage import cleanup_tmp

logger = logging.getLogger(__name__)
CLEANUP_INTERVAL = 60


async def cleanup_once():
    try:
        await asyncio.to_thread(cleanup_tmp)
    except Exception:
        logger.exception("Ошибка очистки временных фотографий")


async def cleanup_loop():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        await cleanup_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Удаляем просроченные файлы, оставшиеся после остановки.
    await cleanup_once()
    task = asyncio.create_task(cleanup_loop())

    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        utils.dadata.close()