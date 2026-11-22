from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


CategorySort = Literal["asc", "desc", "new", "old"]

class CategoryCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    image_path: str = Field( pattern=r"^[0-9a-f]{32}(\.(jpg|png|webp))?$")

class CategoryUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)] | None = None
    image_path: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}(\.(jpg|png|webp))?$")

class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    image_url: str | None
    count_products: int