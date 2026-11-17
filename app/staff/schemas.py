from app.orders.schemas import OrderResponse
from app.staff.models import CompletionStatusEnum


class StaffOrderResponse(OrderResponse):
    completion_status: CompletionStatusEnum
