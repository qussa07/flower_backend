from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Computed, DateTime, ForeignKey, Index, Integer, Numeric, String, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import deferred, relationship

from sqlalchemy import select
from sqlalchemy.orm import column_property

from app.categories.models import Categories

from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True)
    category_title = column_property(
        select(Categories.title)
        .where(Categories.id == category_id)
        .correlate_except(Categories)
        .scalar_subquery(),
        deferred=True,)
    title = Column(String, index=True, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    is_show = Column(Boolean, nullable=False)
    count = Column(Integer, nullable=False, server_default=text("0"))
    is_ready = Column(Boolean, nullable=False, server_default=text("false"))
    description = Column(String(255), nullable=True)
    image_paths = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)  # без скобок
    reserved_count = Column(Integer, nullable=False, server_default=text("0"))

    # заполняется самой БД, из кода не трогаем
    search = deferred(
        Column(
            TSVECTOR,
            Computed(
                "setweight(to_tsvector('russian', coalesce(title, '')), 'A') ",  #"setweight(to_tsvector('russian', coalesce(description, '')), 'B')"
                persisted=True,
            ),
        )
    )

    compounds = relationship(
        "CompoundProduct",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("count >= 0", name="ck_products_count_nonnegative"),
        Index("products_search_idx", "search", postgresql_using="gin"),
        Index(
            "products_title_trgm_idx",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        CheckConstraint("reserved_count >= 0 AND reserved_count <= count",
                        name="ck_products_reserved_count",),
    )


class CompoundProduct(Base):
    __tablename__ = "compounds"

    id =  Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title = Column(String(16), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow) 

    search = deferred(
        Column(
            TSVECTOR,
            Computed("to_tsvector('russian', coalesce(title, ''))", persisted=True),
        )
    )

    product = relationship("Product", back_populates="compounds")

    __table_args__ = (
        Index("compounds_search_idx", "search", postgresql_using="gin"),
        Index(
            "compounds_name_trgm_idx",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )