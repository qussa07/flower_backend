from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


EmailAddress = Annotated[EmailStr, Field(max_length=254)]
Password = Annotated[str, Field(min_length=8, max_length=25)]


class RegUsersModels(BaseModel):
    email: EmailAddress
    name: str = Field(min_length=2, max_length=30)
    password: Password


class VerifyEmailRequest(BaseModel):
    registration_id: str
    code: str = Field(pattern=r"^[0-9]{6}$", min_length=6, max_length=6)

class ResendEmailRequest(BaseModel):
    registration_id: str

class LoginUserModels(BaseModel):
    email: EmailAddress
    password: Password