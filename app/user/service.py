from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import getdb
from app.user.schemas import UserSort, UserRole
from app.user.models import User
import pagination

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