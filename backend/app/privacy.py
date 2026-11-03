"""Keep patient data and authentication material out of application logs."""

import logging

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


def configure_private_logging() -> None:
    # Access URLs contain patient IDs/search terms; ASGI tracing contains headers/bodies.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.asgi").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class PrivateHTTPMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def private_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                if scope["path"].startswith("/api/patients"):
                    MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, private_send)
        except Exception:
            # Exception text/tracebacks can contain SQL values or response-validation data.
            logger.error("HTTP request failed; sensitive error details suppressed.")
            if not response_started:
                response = JSONResponse(
                    {"detail": "Internal server error"},
                    status_code=500,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
