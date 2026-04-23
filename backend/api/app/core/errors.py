from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


async def app_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    # Handle unexpected exceptions
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
