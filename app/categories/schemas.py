from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


CategorySort = Literal["asc", "desc", "new", "old"]

class CategoryCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    image_path: str = Field(pattern=r"^[0-9a-f]{32}(\.(jpg|png|webp))?$")

    @field_validator("image_path", mode="before")
    @classmethod
    def normalize_image_path(cls, value: object) -> object:
        if isinstance(value, str):
            return value.removeprefix("/files/tmp/")
        return value

class CategoryUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)] | None = None
    image_path: str | None = Field(default=None,pattern=r"^(?:/files/(?:tmp|category)/)?[0-9a-f]{32}(\.(jpg|png|webp))?$",)
    
    @field_validator("image_path", mode="before")
    @classmethod
    def normalize_image_path(cls, value: object) -> object:
        if isinstance(value, str):
            return value.removeprefix("/files/tmp/")
        return value

class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    image_path: str | None
    count_products: int