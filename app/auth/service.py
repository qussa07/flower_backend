from uuid import UUID

from sqlalchemy.orm import Session
from .schemas import RegUsersModels, LoginUserModels
from ..user.models import User
from fastapi import HTTPException ,Response, Cookie
import utils

class AuthService:
    def __init__(self, db: Session):
        self.db = db


    def _set_cookie(self, response: Response, refresh: str):
        response.set_cookie(
                key="refresh_token",
                value=refresh,
                httponly=True,
                secure=False, #временно 
                samesite="lax",
                max_age=7 * 24 * 60 * 60,
                path="/auth"
            )

    def register(self, form: RegUsersModels, response: Response):
        user_exists = self.db.query(User).filter(
                User.phone_number == form.phone_number
        ).first()
        if user_exists:
            raise HTTPException(status_code=400, detail="User already exists")
        new_user = User(
            password=utils.hashed_password(form.password),
            phone_number=form.phone_number,
            name=form.name
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        access, refresh = utils.create_access_token(new_user.id), utils.create_refresh_token(new_user.id)
        self._set_cookie(response, refresh)
        return {"access_token": access}


    def login(self, form: LoginUserModels, response: Response):
        user = self.db.query(User).filter(User.phone_number == form.phone_number).first()
        if not user or not utils.verify_password(form.password, user.password):
            raise HTTPException(status_code=404, detail="Invalid phone or password")
        access, refresh = utils.create_access_token(user.id), utils.create_refresh_token(user.id)
        self._set_cookie(response, refresh)
        return {"access_token": access}

    def refresh(self, response: Response, refresh_token: Cookie):
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Token is missing")
        
        data = utils.verify_refresh_token(refresh_token)
        if not data:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        subject = data.get("sub")
        if not isinstance(subject, str):
            raise HTTPException(status_code=401, detail="Invalid token")
        try:
            user_id = UUID(subject)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid token") from None
        
        access = utils.create_access_token(user_id)
        refresh = utils.create_refresh_token(user_id)
        
        self._set_cookie(response, refresh)
        
        return {"access_token": access}

    def logout(self, response: Response, refresh_token: str | None = Cookie(default=None, alias="refresh_token")):
        if not refresh_token:
            raise HTTPException( status_code=401, detail="No active session to logout")

        data = utils.verify_refresh_token(refresh_token)
        if not data:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
    
        response.delete_cookie(
            key="refresh_token",
            path="/auth"
        )
    
        return {"status": "success", "message": "You logout"}

    