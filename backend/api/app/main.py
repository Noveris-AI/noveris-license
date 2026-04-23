import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppException, app_exception_handler, http_exception_handler
from app.modules.issue.models import Base, engine
from app.modules.issue.routes import router as issue_router
from app.modules.verify.routes import router as verify_router

logger = logging.getLogger("naviam.startup")
LOCALHOST_ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.debug:
        if not settings.session_secure:
            logger.warning(
                "[SECURITY] SESSION_SECURE=false in non-debug mode. "
                "Cookies will be sent over HTTP. Set SESSION_SECURE=true in production."
            )
        if settings.allowed_origins == LOCALHOST_ALLOWED_ORIGINS:
            logger.warning(
                "[SECURITY] ALLOWED_ORIGINS is still using localhost defaults in non-debug mode. "
                "Set ALLOWED_ORIGINS to your actual production domain."
            )

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Naviam License API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, app_exception_handler)

app.include_router(issue_router, prefix="/api/v1", tags=["license"])
app.include_router(verify_router, prefix="/api/v1", tags=["verify"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
