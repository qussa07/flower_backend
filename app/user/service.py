from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import getdb
from app.user.schemas import UserSort, UserRole, UserUpdate
from app.user.models import User
import pagination
import utils

router = APIRouter(prefix="/staff", tags=["Staff"])


def get_user_service(db: Session = Depends(getdb)):
    return UserService(db)



class UserService:
    def __init__(self, db):
        self.db = db


    def get_users(self, page: int, perPage: int, search: str = "", role: UserRole = None, sort: UserSort = "new"):
        ordering = {
        "asc": User.name.asc(),
        "desc": User.name.desc(),
        "new": User.created_at.desc(),
        "old": User.created_at.asc(),
        }

        query = self.db.query(User)

        if role is not None:
            query = query.filter(User.role == role)

        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )

        return pagination.paginate(
            query
            .order_by(ordering[sort], User.id.asc()), page, perPage)


    def update_user(self, form: UserUpdate, user_id: UUID) -> User:
        changing_password = form.password is not None
        user = self.db.get(
            User,
            user_id,
            with_for_update=changing_password,
            populate_existing=changing_password,
        )
        if user is None:
            raise HTTPException(404, "Пользователь не найден")

        if form.password is not None and form.current_password is not None:
            if not utils.verify_password(form.current_password, user.password):
                raise HTTPException(400, "Текущий пароль неверный")
            user.password = utils.hashed_password(form.password)

        if form.name is not None:
            user.name = form.name

        self.db.commit()
        self.db.refresh(user)
        return user
        