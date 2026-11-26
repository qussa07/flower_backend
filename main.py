from os import getenv

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.auth.router import router as auth_router
from app.user.router import router as profile_router
from app.product.router import router as product_router
from app.orders.router import router as orders_router
from app.staff.router import router as staff_router
from app.categories.router import router as categories_router
from app.user.models import *
from app.product.models import *
from app.orders.models import *
from fastapi.staticfiles import StaticFiles
from app.product.storage import PRODUCT_DIR, CATEGORY_DIR, TMP_DIR
from app.categories.models import Categories
from app.errors import validation_error_handler
from database import create_tables
from lib.file_system import lifespan
from fastapi.middleware.cors import CORSMiddleware
from app.uploads.router import router as uploads_router



client_port = getenv("CLIENT_PRT", "3000")
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:{client_port}".format(client_port=client_port)],
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_exception_handler(RequestValidationError, validation_error_handler)
create_tables()
app.mount(
    "/files/product",
    StaticFiles(directory=PRODUCT_DIR),
    name="product_photos",
)

app.mount(
    "/files/category",
    StaticFiles(directory=CATEGORY_DIR),
    name="category_photos",
)


app.mount(
    "/files/tmp",
    StaticFiles(directory=TMP_DIR),
    name="tmp_files",
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(product_router)
app.include_router(orders_router)
app.include_router(categories_router)
app.include_router(staff_router)
app.include_router(uploads_router)