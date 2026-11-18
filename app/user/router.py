from fastapi import APIRouter, Depends, HTTPException, Cookie, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from database import getdb
from .models import User
import utils
from sqlalchemy.exc import IntegrityError
from .schemas import UserUpdate



router = APIRouter(prefix="/profile", tags=['Profile'])

@router.get("")
def get_profile(user: User = Depends(utils.get_current_user)):
    return jsonable_encoder(user, exclude={"password"})

@router.patch("")
def update_profile(
    form: UserUpdate,
    user: User = Depends(utils.get_current_user),
    db: Session = Depends(getdb),
):
    changes = form.model_dump(exclude_unset=True)
    if "phone_number" in changes:
        existing = db.query(User).filter(
            User.phone_number == changes["phone_number"], User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Этот номер телефона уже используется")

    for field, value in changes.items():
        if field == "password":
            value = utils.hashed_password(value)
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(status_code=409, detail="Этот номер телефона уже используется") from exc
        raise
    db.refresh(user)
    return jsonable_encoder(user, exclude={"password"})
