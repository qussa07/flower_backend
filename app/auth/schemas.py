from pydantic import BaseModel, Field

class LoginUserModels(BaseModel):
    phone_number: str = Field(pattern=r"^\+7\d{10}$")
    password: str = Field(min_length= 8, max_length=25)


class RegUsersModels(LoginUserModels):
    phone_number: str = Field(pattern=r"^\+7\d{10}$")
    password: str = Field(min_length= 8, max_length=25)
    name: str = Field(min_length=2, max_length=30)