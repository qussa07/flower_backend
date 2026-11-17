
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, String, text
from sqlalchemy.dialects.postgresql import UUID

from database import Base
from .schemas import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    password = Column(String(60), nullable=False)
    phone_number = Column(String(16), unique=True, index=True, nullable=False)
    name = Column(String(30), nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.CUSTOMER)
    created_at = Column(DateTime, default=datetime.utcnow)