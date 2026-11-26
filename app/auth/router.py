from fastapi import APIRouter, Depends, HTTPException, Cookie, Response
from sqlalchemy.orm import Session
from database import getdb
from uuid import UUID
from .schemas import RegUsersModels, LoginUserModels, VerifyEmailRequest
from .service import AuthService



router = APIRouter(prefix="/auth", tags=['Auth'])

def get_user_service(db: Session = Depends(getdb)):
    return AuthService(db)

@router.post("/register")
def register(data: RegUsersModels, service: AuthService = Depends(get_user_service)):
    return service.register(data)

@router.post("/verify")
def verify_email(
    data: VerifyEmailRequest,
    response: Response,
    service: AuthService = Depends(get_user_service),
):
    return service.verify_email(data, response)


@router.post("/login")
def login(response: Response, form: LoginUserModels, service: AuthService = Depends(get_user_service)):
    return service.login(form, response)


@router.post("/resend")
def resend(registration_id: UUID, service: AuthService = Depends(get_user_service),):
    return service.resend(registration_id)


@router.post("/refresh")
def refresh_session(response: Response, refresh_token: str | None = Cookie(default=None, alias="refresh_token"), service: AuthService = Depends(get_user_service)):
    return service.refresh(response, refresh_token)


@router.post("/logout")
def logout(response: Response, refresh_token: str | None = Cookie(default=None, alias="refresh_token"), service: AuthService = Depends(get_user_service)):
    return service.logout(response, refresh_token)

