from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError


UserSort = Literal["asc", "desc", "new", "old"]

class UserRole(Enum):
    CUSTOMER = "customer"
    MANAGER = "manager"
    ADMIN = "admin"


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=30)
    password: Annotated[
        str, StringConstraints(strip_whitespace=False)
    ] | None = Field(default=None, min_length=8, max_length=25)
    current_password: Annotated[
        str, StringConstraints(strip_whitespace=False)
    ] | None = Field(default=None, min_length=8, max_length=25)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise PydanticCustomError(
                "request_value_invalid", "Укажите поля для обновления профиля"
            )
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise PydanticCustomError(
                "request_value_invalid", "Переданные поля должны содержать значения"
            )
        if (self.password is None) != (self.current_password is None):
            raise PydanticCustomError(
                "request_value_invalid", "Укажите текущий и новый пароль"
            )
        for value in (self.password, self.current_password):
            if value is not None and len(value.encode("utf-8")) > 72:
                raise PydanticCustomError(
                    "request_value_invalid", "Пароль должен занимать не больше 72 байт"
                )
        return self



class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: UserRole
    created_at: datetime