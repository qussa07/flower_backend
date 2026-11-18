from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator, EmailStr
from pydantic_core import PydanticCustomError


class DeliveryMethod(str, Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: int = Field(gt=0, le=999)


class OrdersModels(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)
    customer_name: str = Field(min_length=1, max_length=30)
    customer_phone: str = Field(pattern=r"^\+7\d{10}$")
    customer_email: EmailStr
    recipient_name: str = Field(min_length=1, max_length=100)
    recipient_phone: str = Field(pattern=r"^\+7\d{10}$")
    delivery_method: DeliveryMethod
    delivery_date: date
    delivery_time_start: time
    delivery_time_end: time
    shipping_address: str | None = Field(default=None, max_length=2000)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("delivery_time_start", "delivery_time_end")
    @classmethod
    def validate_local_time(cls, value):
        if value.tzinfo is not None:
            raise PydanticCustomError("request_value_invalid", "Укажите время доставки без часового пояса")
        return value

    @model_validator(mode="after")
    def validate_order(self):
        if self.delivery_time_start >= self.delivery_time_end:
            raise PydanticCustomError("request_value_invalid", "Время начала доставки должно быть раньше окончания")
        if self.delivery_method == DeliveryMethod.DELIVERY and not self.shipping_address:
            raise PydanticCustomError("request_value_invalid", "Укажите адрес доставки")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise PydanticCustomError("request_value_invalid", "Объедините одинаковые товары в одну позицию заказа")
        return self


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    product_title: str
    quantity: int
    unit_price: Decimal

    @computed_field
    @property
    def total_price(self) -> Decimal:
        return self.unit_price * self.quantity


class OrderResponseAll(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: int
    created_at: datetime
    payment_status: PaymentStatus
    total_amount: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: int
    created_at: datetime
    payment_status: PaymentStatus
    total_amount: Decimal
    items: list[OrderItemResponse]

    customer_name: str
    customer_phone: str
    customer_email: str | None
    recipient_name: str
    recipient_phone: str
    delivery_method: DeliveryMethod
    delivery_date: date
    delivery_time_start: time
    delivery_time_end: time
    shipping_address: str | None
    comment: str | None


class PaymentObject(BaseModel):
    id: UUID


class PaymentNotification(BaseModel):
    type: str
    event: str
    object: PaymentObject
