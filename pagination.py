from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    perPage: int
    currentPage: int
    lastPage: int
    total: int
    isNext: bool
    isPrev: bool


class Page(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta



def paginate(query, page: int, per_page: int):
    total = query.order_by(None).count()
    last_page = max(1, (total + per_page - 1) // per_page)

    items = (
        query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "data": items,
        "meta": {
            "perPage": per_page,
            "currentPage": page,
            "lastPage": last_page,
            "total": total,
            "isNext": page < last_page,
            "isPrev": page > 1,
        },
    }