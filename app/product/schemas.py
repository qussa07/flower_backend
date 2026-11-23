from pydantic import BaseModel, Field, StringConstraints
from decimal import Decimal
from uuid import UUID
from typing import Annotated, Literal

PhotoId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}(\.(jpg|png|webp))?$")]
ProductSort = Literal["new", "old", "cheap", "expensive", "asc", "desc", "price_asc", "price_desc"]

class CompositionItem(BaseModel):
    title: str = Field(min_length=1, max_length=16)
    quantity: int = Field(gt=0, le=2147483647)

class ProductModels(BaseModel):
    category_id: UUID | None = None
    title: str = Field(min_length=5, max_length=50)
    price: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        allow_inf_nan=False,)
    count: int = Field(ge=0, le=2147483647)
    is_show: bool
    is_show_case: bool
    compounds: list[CompositionItem]
    image_paths: list[str] = Field(default_factory=list, max_length=5)
    description: str = Field(max_length=255)


class ProductUpdate(ProductModels):
    image_paths: list[str] | None =  Field(default=None, max_length=5)


class ProductSearchParams(BaseModel):
    string: str | None = Field(
        default=None, 
        description="Строка для поиска по названию или описанию"
    )
    # Дополнительные параметры (пример)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    sort: ProductSort | None = None
    per_page: int = Field(default=20, ge=1, le=100)
    page: int = Field(default=1, ge=1)