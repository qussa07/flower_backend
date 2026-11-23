from datetime import datetime
from sqlalchemy import Column, DateTime, Enum, String, text
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Categories(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title = Column(String(20), nullable=False)
    image_path = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow) 