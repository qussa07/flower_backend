from uuid import UUID

from datetime import datetime, timezone

from hashlib import sha256

from sqlalchemy import func, update, text

from database import get_redis

from .mail import send_verification_code
from .otp import SEND_COOLDOWN, check_code, delete_code, generate_code, is_on_cooldown, issue_code, get_registration_email, replace_code
from .schemas import LoginUserModels, RegUsersModels, VerifyEmailRequest

from sqlalchemy import func
from sqlalchemy.orm import Session
from .schemas import RegUsersModels, LoginUserModels
from ..user.models import User
from fastapi import HTTPException ,Response, Cookie
import utils

from sqlalchemy.exc import IntegrityError

class AuthService:
    def __init__(self, db: Session):
        self.db = db


    @staticmethod
    def _verification_session(session_id: str, password_hash: str) -> str:
        return sha256(f"{session_id}:{password_hash}".encode("utf-8")).hexdigest()


    def _set_cookie(self, response: Response, refresh: str):
        response.set_cookie(
                key="refresh_token",
                value=refresh,
                httponly=True,
                secure=False, #временно 
                samesite="lax",
                max_age=7 * 24 * 60 * 60,
                path="/"
            )

    def register(self, form: RegUsersModels):
        email = form.email.lower()

        try:
            acquired = self.db.execute(
                text("SELECT pg_try_advisory_xact_lock(hashtextextended(:email, 0))"),
                {"email": email},
            ).scalar_one()

            if not acquired or is_on_cooldown(email):
                raise HTTPException(
                    status_code=429,
                    detail="Подожди перед повторной отправкой",
                )
            user = (
                self.db.query(User)
                .filter(func.lower(User.email) == email)
                .with_for_update()
                .one_or_none()
            )

            if user is None:
                self.db.add(User(
                    email=email,
                    name=form.name,
                    password=utils.hashed_password(form.password),
                ))
            elif user.email_verified_at is not None:
                raise HTTPException(status_code=409, detail="Email уже используется")
            elif not utils.verify_password(form.password, user.password):
                raise HTTPException(
                    status_code=409,
                    detail="По этому email уже начата регистрация",
                )

            code = generate_code()
            try:
                send_verification_code(email, code)
            except OSError as exc:
                self.db.rollback()
                raise HTTPException(
                    status_code=503,
                    detail="Не удалось отправить письмо. Попробуй ещё раз",
                ) from exc

            self.db.flush()

            issued = issue_code(email, code)
            if issued is None:
                self.db.rollback()
                raise HTTPException(
                    status_code=429,
                    detail="Подожди перед повторной отправкой",
                )

            registration_id, _ = issued
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "uq_users_email_lower":
                raise HTTPException(status_code=409, detail="Email уже используется") from exc
            raise

        return {"registration_id": str(registration_id)}


    def resend(self, registration_id: UUID):
        email = get_registration_email(registration_id)
        if email is None:
            raise HTTPException(400, "Регистрация не найдена или истекла")

        user = self.db.query(User).filter(User.email == email).one_or_none()
        if user is None or user.email_verified_at is not None:
            raise HTTPException(400, "Регистрация больше не ожидает подтверждения")

        cooldown_key = f"otp:cooldown:{email.lower()}"
        if not get_redis().set(cooldown_key, "1", nx=True, ex=SEND_COOLDOWN):
            raise HTTPException(429, "Подожди перед повторной отправкой")

        code = generate_code()
        try:
            send_verification_code(email, code)
        except OSError as exc:
            raise HTTPException(503, "Не удалось отправить письмо") from exc

        if not replace_code(registration_id, code):
            raise HTTPException(400, "Регистрация не найдена или истекла")

        return {"registration_id": str(registration_id)}

    def verify_email(self, form: VerifyEmailRequest, response: Response):
        email = check_code(form.registration_id, form.code)
        if email is None:
            raise HTTPException(
                status_code=400,
                detail="Код неверный, просрочен или попытки закончились",
            )

        user_id = self.db.execute(
            update(User)
            .where(User.email == email, User.email_verified_at.is_(None))
            .values(email_verified_at=datetime.now(timezone.utc))
            .returning(User.id)
        ).scalar_one_or_none()

        if user_id is None:
            raise HTTPException(
                status_code=409,
                detail="Аккаунт уже подтверждён или не найден",
            )

        self.db.commit()
        delete_code(form.registration_id)
        self._set_cookie(response, utils.create_refresh_token(user_id))
        return {"access": utils.create_access_token(user_id)}


    def login(self, form: LoginUserModels, response: Response):
        user = self.db.query(User).filter(
            func.lower(User.email) == func.lower(form.email)).one_or_none()
        
        if user is None or not utils.verify_password(form.password, user.password):
            raise HTTPException(status_code=404, detail="Неверный email или пароль")
        if user.email_verified_at is None:
                raise HTTPException(status_code=403, detail="Подтвердите электронную почту")
        access, refresh = utils.create_access_token(user.id), utils.create_refresh_token(user.id)
        self._set_cookie(response, refresh)
        return {"access_token": access}

    def refresh(self, response: Response, refresh_token: Cookie):
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Токен не передан")
        
        data = utils.verify_refresh_token(refresh_token)
        if not data:
            raise HTTPException(status_code=401, detail="Недействительный токен")

        subject = data.get("sub")
        if not isinstance(subject, str):
            raise HTTPException(status_code=401, detail="Недействительный токен")
        try:
            user_id = UUID(subject)
        except ValueError:
            raise HTTPException(status_code=401, detail="Недействительный токен") from None
        user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        access = utils.create_access_token(user_id)
        refresh = utils.create_refresh_token(user_id)
        
        self._set_cookie(response, refresh)
        
        return {"access_token": access,
                "role": user.role,}

    def logout(self, response: Response, refresh_token: str | None = Cookie(default=None, alias="refresh_token")):
        if not refresh_token:
            raise HTTPException( status_code=401, detail="Нет активной сессии для выхода")

        data = utils.verify_refresh_token(refresh_token)
        if not data:
            raise HTTPException(status_code=401, detail="Сессия недействительна или истекла")
    
        response.delete_cookie(
            key="refresh_token",
            path="/"
        )
    
        return {"status": "success", "message": "You logout"}

    