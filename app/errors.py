from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []

    for error in exc.errors():
        location = error["loc"]
        source = location[0] if location else "request"
        field_parts = (
            location[1:]
            if location and location[0] in {"body", "query", "path", "header"}
            else location
        )
        field = ".".join(map(str, field_parts)) or source

        message = error["msg"]

        errors.append({"field": field, "message": message})

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )   