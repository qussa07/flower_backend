from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


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
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Fields cannot be null")
        return self
