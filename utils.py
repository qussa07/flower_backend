import bcrypt
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
from fastapi import Query, WebSocketException
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.user.models import User
import database
import os
import uuid
import ipaddress
from uuid import UUID
from app.user.schemas import UserRole
import httpx
from dadata import Dadata
import warnings
from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_PIXELS = 25_000_000

IMAGE_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

KAZAN_KLADR_ID = "1600000100000"
load_dotenv()
DADATA_API_KEY = os.environ["DADATA_API_KEY"]
DADATA_SECRET_KEY = os.environ["DADATA_SECRET_KEY"]
URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
dadata = Dadata(DADATA_API_KEY, DADATA_SECRET_KEY, timeout=10)

YOOKASSA_NETS = [ipaddress.ip_network(n) for n in (
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "77.75.154.128/25",
    "2a02:5180::/32",
)]
SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTE"))
ALGORITHM = os.getenv("ALGORITHM")
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))

def hashed_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def create_access_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTE)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return HTTPException(status_code=401, detail="Invalid token")
    except jwt.InvalidTokenError:
        return HTTPException(status_code=401, detail="Invalid token")


def create_refresh_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh", "jti": jti}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_refresh_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('type') != "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.getdb)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if not isinstance(user_id, str):
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = db.query(User).filter(User.id == parsed_user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_role(*roles: UserRole):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        return user
    return checker

require_admin = require_role(UserRole.ADMIN)
require_staff = require_role(UserRole.ADMIN, UserRole.MANAGER)

def is_yookassa_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in YOOKASSA_NETS)


def check_adress(address: str) -> str:
    """Проверить выбранный адрес доставки в Казани."""

    try:
        suggestions = dadata.suggest(
            name="address",
            query=address,
            count=1,
            locations=[{"kladr_id": KAZAN_KLADR_ID}],
            )
    except httpx.HTTPError:
        return "service_unavailable"

    if not suggestions:
        return "not_found"

    data = suggestions[0].get("data") or {}

    if data.get("city_kladr_id") != KAZAN_KLADR_ID:
        return "out_of_zone"

    if not data.get("house"):
        return "need_house_number"

    return "ok"


def require_staff_ws(
    token: str | None = Query(default=None),
) -> UUID:
    if not token:
        raise WebSocketException(
            code=1008,
            reason="Missing token",
        )

    try:
        with database.SessionLocal() as db:
            user = get_current_user(token=token, db=db)
            require_staff(user=user)
            user_id = user.id

        return user_id

    except HTTPException as exc:
        raise WebSocketException(
            code=1008,
            reason="Unauthorized or forbidden",
        ) from exc



def paginate(query, page: int, per_page: int):
    total = query.order_by(None).count()
    last_page = max(1, (total + per_page - 1) // per_page)

    items = (
        query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "data": items,
        "meta": {
            "perPage": per_page,
            "currentPage": page,
            "lastPage": last_page,
            "total": total,
            "isNext": page < last_page,
            "isPrev": page > 1,
        },
    }



def validate_image(content: bytes, filename: str) -> str:
    if not content:
        raise HTTPException(400, f"{filename}: файл пустой")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(content)) as image:
                content_type = IMAGE_TYPES.get(image.format)

                if content_type is None:
                    raise HTTPException(
                        400, f"{filename}: разрешены JPEG, PNG и WebP"
                    )

                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(
                        400, f"{filename}: разрешение больше 25 мегапикселей"
                    )

                # Проверяем целостность структуры файла.
                image.verify()

            # После verify изображение нужно открыть заново.
            with Image.open(BytesIO(content)) as image:
                image.load()

    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(
            400, f"{filename}: слишком большое разрешение"
        ) from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise HTTPException(
            400, f"{filename}: повреждённый файл или не изображение"
        ) from None

    return content_type