from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base
from .schemas import DeliveryMethod, PaymentStatus
from app.staff.models import CompletionStatusEnum


def enum_values(enum_class):
    return [item.value for item in enum_class]


class Orders(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    number = Column(BigInteger, Identity(start=1000), nullable=False, unique=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    customer_name = Column(String(30), nullable=False)
    customer_phone = Column(String(16), nullable=False)
    customer_email = Column(String(254), nullable=True)
    recipient_name = Column(String(100), nullable=False)
    recipient_phone = Column(String(16), nullable=False)

    delivery_method = Column(
        Enum(DeliveryMethod, name="delivery_method", values_callable=enum_values),
        nullable=False,
    )
    delivery_date = Column(Date, nullable=False)
    delivery_time_start = Column(Time, nullable=True)
    delivery_time_end = Column(Time, nullable=True)
    shipping_address = Column(String(2000), nullable=True)
    comment = Column(String(2000), nullable=True)

    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_status = Column(
        Enum(PaymentStatus, name="payment_status", values_callable=enum_values),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    payment_id = Column(String(255), nullable=True, unique=True,)
    payment_url = Column(String, nullable=True)
    payment_key = Column(String, nullable=True)
    stock_reserved = Column(Boolean, nullable=False, server_default=text("false"))
    payment_action = Column(String(16), nullable=True)
    completion_status = Column(Enum(CompletionStatusEnum, name="completion_status",
                                    values_callable=enum_values), 
                                    nullable=False,
                                    default=CompletionStatusEnum.IN_PROGRESS)
    expireAt = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    customer = relationship("User")
    items = relationship("OrderItems", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_orders_total_nonnegative"),
        CheckConstraint("delivery_time_start < delivery_time_end", name="ck_orders_delivery_time"),
        CheckConstraint(
            "delivery_method <> 'delivery' OR "
            "(shipping_address IS NOT NULL AND length(trim(shipping_address)) > 0)",
            name="ck_orders_delivery_address",
        ),
    )


class OrderItems(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    product_title = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)

    order = relationship("Orders", back_populates="items")
    product = relationship("Product")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_order_items_price"),
    )


class OrderExpirationOutbox(Base):
    __tablename__ = "order_expiration_outbox"

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    )

    run_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )