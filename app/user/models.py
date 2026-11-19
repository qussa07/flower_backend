
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from database import Base
from .schemas import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(254), nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    password = Column(String(60), nullable=False)
    name = Column(String(30), nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.CUSTOMER)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("uq_users_email_lower", func.lower(email), unique=True),
    )