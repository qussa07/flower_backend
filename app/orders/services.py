from sqlalchemy.orm import Session, selectinload
from decimal import Decimal

import pagination
from ..user.models import User
from fastapi import HTTPException, Request
from pathlib import Path
from uuid import UUID
from sqlalchemy import String, cast, or_
import os
from sqlalchemy import exists, func, or_
from .models import Orders, OrderItems, OrderExpirationOutbox
from app.product.models import Product
from yookassa import Configuration, Payment, invoice
from .schemas import PaymentNotification, PaymentStatus, DeliveryMethod, OrdersModels
import utils
from datetime import datetime, timezone, timedelta
from uuid import uuid4, uuid5, NAMESPACE_URL

Configuration.configure(
    os.getenv("YOOKASSA_SHOP_ID"),
    os.getenv("YOOKASSA_SECRET_KEY"),
)

client_url = os.getenv("CLIENT_URL")

MAX_TOKENS = 8


class OrdersService():
     def __init__(self, db: Session):
               self.db = db

     def get_orders(self, user: User, page: int = 1, perPage: int = 1000):
          query =  (
               self.db.query(Orders)
               .options(selectinload(Orders.items))
               .filter(Orders.customer_id == user.id)
               .order_by(Orders.created_at.desc(), Orders.id.desc())
               .all()
          )
          return pagination.paginate(query, page, perPage)

     def create_order(self, form: OrdersModels, user: User):
          result = None
          if form.delivery_method == DeliveryMethod.DELIVERY:
               if form.shipping_address is None:
                    raise HTTPException(422, "Укажите адрес доставки")
               else:
                    result = utils.check_adress(form.shipping_address)

          if result == "service_unavailable":
               raise HTTPException(
                status_code=503,
                detail="Не удалось проверить адрес. Попробуйте позже.",
            )
          errors = {
          "not_found": "Адрес в Казани не найден. Проверьте адрес.",
          "out_of_zone": "Доставка доступна только в пределах Казани.",
          "need_house_number": "Укажите номер дома.",
          }

          if result in errors:
               raise HTTPException(status_code=422, detail=errors[result])
          order = Orders(
                         customer_id=user.id,  
                         customer_name=form.customer_name,
                         customer_phone=form.customer_phone,
                         customer_email=form.customer_email,
                         recipient_name=form.recipient_name,
                         recipient_phone=form.recipient_phone,
                         delivery_method=form.delivery_method,
                         delivery_date=form.delivery_date,
                         delivery_time_start=form.delivery_time_start,
                         delivery_time_end=form.delivery_time_end,
                         shipping_address=form.shipping_address,
                         expireAt=datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("ORDER_PAYMENT_TIMEOUT_MINUTES"))),
                         payment_key=str(uuid4()),
                         comment=form.comment
                    )
          try:
               self.reserve_order_items(order, form.items)
               self.db.add(order)

               # Выполняем INSERT и получаем созданный PostgreSQL UUID.
               self.db.flush()

               """self.db.add(
                    OrderExpirationOutbox(
                         order_id=order.id,
                         run_at=order.expireAt,
                    )
               )"""

               # Заказ, резерв и задание фиксируются вместе.
               self.db.commit()

          except Exception:
               self.db.rollback()
               raise

          self.db.refresh(order)
          return {"id": order.id}

     """def finish_reservation(self, order: Orders, *, sold: bool):
          #Освободить резерв или завершить продажу, без commit().
          if not order.stock_reserved:
               return

          quantities = {
               item.product_id: item.quantity
               for item in order.items
          }

          products = (
               self.db.query(Product)
               .filter(Product.id.in_(quantities))
               .order_by(Product.id)
               .populate_existing()
               .with_for_update()
               .all()
          )

          if len(products) != len(quantities):
               raise RuntimeError("Не найдены товары зарезервированного заказа")

          for product in products:
               if product.reserved_count < quantities[product.id]:
                    raise RuntimeError(
                         f"Нарушен учёт резерва товара {product.id}"
                    )

          for product in products:
               quantity = quantities[product.id]

               product.reserved_count -= quantity

               if sold:
                    product.count -= quantity

          order.stock_reserved = False"""

     
     def get_order(self, user: User, order_id: UUID):
          order = (
               self.db.query(Orders)
               .options(selectinload(Orders.items))
               .filter(
                    Orders.id == order_id,
                    Orders.customer_id == user.id,
               )
               .first()
          )

          if order is None:
               raise HTTPException(404, "Заказ не найден")

          return order


     def reserve_order_items(self, order: Orders, items):
           # Зарезервировать товары для нового заказа без commit().
          product_ids = [item.product_id for item in items]

          # Блокируем товары на время транзакции.
          products = (
               self.db.query(Product)
               .filter(Product.id.in_(product_ids))
               .order_by(Product.id)
               .populate_existing()
               .with_for_update()
               .all()
          )

          products_by_id = {product.id: product for product in products}

          # Сначала проверяем все позиции.
          for item in items:
               product = products_by_id.get(item.product_id)

               if product is None:
                    raise HTTPException(404, "Товар не найден")

               if not product.is_show:
                    raise HTTPException(
                         409,
                         f"Товар недоступен: {product.title}",
                    )

               # available = product.count - product.reserved_count
               available = product.count

               if available < item.quantity:
                    raise HTTPException(
                         409,
                         f"Недостаточно товара: {product.title}. "
                         f"Доступно: {available}",
                    )

          # Затем резервируем и формируем позиции заказа.
          total_amount = Decimal("0.00")

          for item in items:
               product = products_by_id[item.product_id]

               # product.reserved_count += item.quantity

               order.items.append(
                    OrderItems(
                         product_id=product.id,
                         product_title=product.title,
                         quantity=item.quantity,
                         unit_price=product.price,
                    )
               )

               total_amount += product.price * item.quantity

          order.total_amount = total_amount
          # order.stock_reserved = True

     """"def reserve_order_items(self, order: Orders, items):
           # Зарезервировать товары для нового заказа без commit().
          product_ids = [item.product_id for item in items]

          # Блокируем товары на время транзакции.
          products = (
               self.db.query(Product)
               .filter(Product.id.in_(product_ids))
               .order_by(Product.id)
               .populate_existing()
               .with_for_update()
               .all()
          )

          products_by_id = {product.id: product for product in products}

          # Сначала проверяем все позиции.
          for item in items:
               product = products_by_id.get(item.product_id)

               if product is None:
                    raise HTTPException(404, "Товар не найден")

               if not product.is_show:
                    raise HTTPException(
                         409,
                         f"Товар недоступен: {product.title}",
                    )

               available = product.count - product.reserved_count

               if available < item.quantity:
                    raise HTTPException(
                         409,
                         f"Недостаточно товара: {product.title}. "
                         f"Доступно: {available}",
                    )

          # Затем резервируем и формируем позиции заказа.
          total_amount = Decimal("0.00")

          for item in items:
               product = products_by_id[item.product_id]

               product.reserved_count += item.quantity

               order.items.append(
                    OrderItems(
                         product_id=product.id,
                         product_title=product.title,
                         quantity=item.quantity,
                         unit_price=product.price,
                    )
               )

               total_amount += product.price * item.quantity

          order.total_amount = total_amount
          order.stock_reserved = True


     def process_payment(self, payment_id: str):
          def load_order():
               order = (
                    self.db.query(Orders)
                    .filter(Orders.payment_id == payment_id)
                    .populate_existing()
                    .with_for_update()
                    .first()
               )

               if order is None:
                    raise HTTPException(404, "Заказ не найден")

               return order

          def validate_payment(payment, order):
               if (
                    str(payment.id) != str(order.payment_id)
                    or Decimal(str(payment.amount.value)) != order.total_amount
                    or payment.amount.currency != "RUB"
                    or str((payment.metadata or {}).get("order_id")) != str(order.id)
               ):
                    raise HTTPException(409, "Данные платежа не совпадают с данными заказа")

               if (
                    payment.status in ("waiting_for_capture", "succeeded")
                    and payment.paid is not True
               ):
                    raise HTTPException(409, "Платёж не авторизован")

          try:
               payment = Payment.find_one(payment_id)
          except Exception as exc:
               raise HTTPException(502, "Не удалось проверить платёж") from exc

          order = load_order()
          validate_payment(payment, order)

          # Повторное уведомление не должно повторно списать товар.
          # CANCELLED здесь намеренно не пропускаем.
          if order.payment_status in (
               PaymentStatus.PAID,
               PaymentStatus.REFUNDED,
          ):
               self.db.commit()
               return {"status": "ok"}

          if payment.status == "waiting_for_capture":
               # Решение выбираем только один раз.
               if order.payment_action is None:
                    if order.expireAt is None:
                         raise HTTPException(409, "У заказа не указан срок оплаты")

                    can_capture = (
                         order.payment_status == PaymentStatus.PENDING
                         and order.stock_reserved
                         and datetime.now(timezone.utc) < order.expireAt
                    )

                    order.payment_action = "capture" if can_capture else "cancel"

                    if not can_capture:
                         self.finish_reservation(order, sold=False)
                         order.payment_status = PaymentStatus.CANCELLED

               action = order.payment_action

               if action not in ("capture", "cancel"):
                    raise HTTPException(409, "Недопустимое действие с платежом")

               if action == "capture" and (
                    order.payment_status != PaymentStatus.PENDING
                    or not order.stock_reserved
               ):
                    raise HTTPException(409, "Статус заказа не позволяет списать платёж")

               # Сохраняем решение ДО внешнего запроса.
               # При таймауте оно останется в БД.
               self.db.commit()

               operation_key = str(
                    uuid5(NAMESPACE_URL, f"{action}:{payment_id}")
               )

               try:
                    if action == "capture":
                         payment = Payment.capture(
                              payment_id,
                              {},
                              idempotency_key=operation_key,
                         )
                    else:
                         payment = Payment.cancel(
                              payment_id,
                              idempotency_key=operation_key,
                         )
               except Exception as exc:
                    # Не отвечаем "ok": результат пока неизвестен.
                    raise HTTPException(
                         502,
                         "Не удалось получить результат операции с платежом",
                    ) from exc

               # После commit прежняя блокировка снята.
               # Загружаем актуальный заказ и снова блокируем его.
               order = load_order()
               validate_payment(payment, order)

               if order.payment_status in (
                    PaymentStatus.PAID,
                    PaymentStatus.REFUNDED,
               ):
                    self.db.commit()
                    return {"status": "ok"}

          if payment.status == "succeeded":
               if (
                    order.payment_status != PaymentStatus.PENDING
                    or order.payment_action == "cancel"
                    or not order.stock_reserved
               ):
                    # Деньги списаны, но заказ нельзя автоматически выполнить.
                    # Нужны разбор ситуации и, возможно, возврат.
                    raise HTTPException(
                         409,
                         "Платёж списан для заказа без действующего резерва",
                    )

               self.finish_reservation(order, sold=True)
               order.payment_status = PaymentStatus.PAID

          elif payment.status == "canceled":
               self.finish_reservation(order, sold=False)
               order.payment_status = PaymentStatus.CANCELLED
               order.payment_action = None

          self.db.commit()
          return {"status": payment.status}

     
     def webhook(self, notification: PaymentNotification, request: Request):
          ip = request.client.host if request.client else None

          if not ip or not utils.is_yookassa_ip(ip):
               raise HTTPException(403, "Доступ запрещён")

          if notification.event not in (
               "payment.waiting_for_capture",
               "payment.succeeded",
               "payment.canceled",
          ):
               return {"status": "ok"}

          return self.process_payment(str(notification.object.id))


     def _start_payment(self, order: Orders):
          # платёж уже создавали: отдаём ту же ссылку, второй раз не создаём
          if order.payment_url:
               return {"id": order.id, "pay_url": order.payment_url}

          try:
               payment = Payment.create(
                    {
                         "amount": {"value": format(order.total_amount, ".2f"), "currency": "RUB"},
                         "capture": False,
                         "confirmation": {
                              "type": "redirect",
                              "return_url": f"{client_url}/orders/{order.id}",
                         },
                         "description": f"Заказ №{order.number}",
                         "metadata": {"order_id": str(order.id)},
                    },
                    order.payment_key,   # ключ идемпотентности
               )
          except Exception:
               raise HTTPException(502, "Платёжная система недоступна, попробуйте ещё раз")

          order.payment_id = payment.id
          order.payment_url = payment.confirmation.confirmation_url
          self.db.commit()
          return {"id": order.id, "pay_url": order.payment_url}


     def pay(self, order_id, user):
          order = (self.db.query(Orders)
                    .filter(Orders.id == order_id, Orders.customer_id == user.id)
                    .first())
          if order is None:
               raise HTTPException(404, "Заказ не найден")
          if order.payment_status != PaymentStatus.PENDING:
               raise HTTPException(409, "Заказ не ожидает оплаты")
          if order.expireAt < datetime.now(timezone.utc):
               raise HTTPException(409, "Время оплаты истекло")

          return self._start_payment(order)"""