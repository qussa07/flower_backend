from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError


UserSort = Literal["asc", "desc", "new", "old"]

class UserRole(Enum):
    CUSTOMER = "customer"
    MANAGER = "manager"
    ADMIN = "admin"



class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=30)
    phone_number: str | None = Field(default=None, pattern=r"^\+7\d{10}$")

    password: Annotated[str, StringConstraints(strip_whitespace=False)] | None = Field(
        default=None, min_length=8, max_length=25
    )

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise PydanticCustomError("request_value_invalid", "Укажите хотя бы одно поле для обновления профиля")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise PydanticCustomError("request_value_invalid", "Переданные поля профиля должны содержать значения")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone_number: str
    role: UserRole
    created_at: datetime