from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import admin_router, router as auth_router
from app.security import read_jwt_secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    read_jwt_secret()
    yield


app = FastAPI(title="Code Nova - Clinical Management Software", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(admin_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default validation response can echo passwords from request bodies.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {key: error[key] for key in ("type", "loc", "msg")}
                for error in exc.errors()
            ]
        },
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
