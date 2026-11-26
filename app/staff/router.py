from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from app.staff.websocket import manager
from database import getdb
from app.product.schemas import ProductSort
from app.user.service import UserService, get_user_service
from app.staff.schemas import StaffOrderResponse
from app.staff.service import StaffOrdersService
from app.user.models import User
from app.user.schemas import UserResponse, UserSort, UserRole
import pagination
from utils import require_staff, require_staff_ws
from decimal import Decimal

router = APIRouter(prefix="/staff", tags=["Staff"])


def get_staff_service(db: Session = Depends(getdb)):
    return StaffOrdersService(db)


@router.get("", response_model=list[StaffOrderResponse])
def get_orders(
    user: User = Depends(require_staff),
    service: StaffOrdersService = Depends(get_staff_service),
):
    return service.get_orders()

@router.get("/users",response_model=pagination.Page[UserResponse], dependencies=[Depends(require_staff)])
def get_users(page: int= Query(1, ge=1),
    perPage: int = Query(20, ge=1, le=100),
    search: str = "",
    role: UserRole | None = None,
    sort: UserSort = "new",
    service: UserService = Depends(get_user_service)):
    return service.get_users(page, perPage, search, role, sort)


@router.post("/{order_id}/complete", response_model=StaffOrderResponse)
async def complete_order(
    order_id: UUID,
    user: User = Depends(require_staff),
    service: StaffOrdersService = Depends(get_staff_service),
):
    order = await run_in_threadpool(
        service.complete_order,
        order_id
    )

    await manager.broadcast({
        "type": "order.completed"
    })

    return order

@router.get("/stats", dependencies=[Depends(require_staff)])
def get_stats(service: StaffOrdersService = Depends(get_staff_service)):
    return service.stats()

@router.get("/products")
def get_products(page: int = Query(1, ge=1),
    user: User = Depends(require_staff),
    perPage: int = Query(20, ge=1, le=100),
    search: str | None = None,
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    sort: ProductSort | None = None,
    category_ids: list[UUID] | None = Query(default=None),
    is_ready: bool = True,
    is_not_show: bool = False,
    service: StaffOrdersService = Depends(get_staff_service)):
    return service.get_products(page=page, perPage=perPage, search=search, min_price=min_price, max_price=max_price, category_ids=category_ids, sort=sort, is_ready=is_ready
                                , is_not_show=is_not_show)

@router.websocket("/ws")
async def staff_websocket(
    websocket: WebSocket,
    user_id: UUID = Depends(require_staff_ws),
):
    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@router.get("/products/{product_id}", dependencies=[Depends(require_staff)])
def get_staff_product(
    product_id: UUID,
    service: StaffOrdersService = Depends(get_staff_service)
):
    return service.get_product(product_id)