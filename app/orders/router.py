from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import getdb, get_redis
from app.user.models import User
from .services import OrdersService
from uuid import UUID
from fastapi.concurrency import run_in_threadpool
from yookassa import Configuration, Payment
from .schemas import OrderResponseAll, OrdersModels, PaymentNotification, OrderResponse
import os
from uuid import uuid4
import utils
from app.staff.websocket import manager

"""Configuration.configure(
    os.getenv("YOOKASSA_SHOP_ID"),
    os.getenv("YOOKASSA_SECRET_KEY"))"""

router = APIRouter(prefix="/orders", tags=["Orders"])


def get_user_service(db: Session = Depends(getdb)):
    return OrdersService(db)

@router.post('/')
def create_orders(form: OrdersModels,user: User = Depends(utils.get_current_user), service: OrdersService = Depends(get_user_service)):
    return service.create_order(form, user)

@router.get('/', response_model=list[OrderResponseAll])
def get_orders(user: User = Depends(utils.get_current_user), service: OrdersService = Depends(get_user_service)):
    return service.get_orders(user)

@router.get('/{order_id}', response_model=OrderResponse)
def get_order(order_id: UUID, user: User = Depends(utils.get_current_user), service: OrdersService = Depends(get_user_service)):
    return service.get_order(user, order_id)

"""@router.post("/{order_id}/pay")
def pay_order(order_id: UUID, user: User = Depends(utils.get_current_user),
              service: OrdersService = Depends(get_user_service)):
    return service.pay(order_id, user)"""
"""
@router.post("/webhook")
async def webhook(request: Request, notification: PaymentNotification,service: OrdersService = Depends(get_user_service)):
    result = await run_in_threadpool(service.webhook, 
                                     notification, 
                                     request)
    if result.get("status") == "succeeded":
        await manager.broadcast({"type": "orders.updated"})

    return {"status": "ok"} """