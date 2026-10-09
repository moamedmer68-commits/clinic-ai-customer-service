import hmac
import logging
import os
import re
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field

load_dotenv()

from agent import DoctorAppointmentAgent
from utils.session import make_thread_id


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)
logger = logging.getLogger(__name__)

_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,64}")


class UserQuery(BaseModel):
    id_number: int = Field(..., ge=1000000, le=99999999)
    messages: str = Field(..., min_length=1, max_length=10_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


logger.addFilter(RequestIdFilter())
for _handler in logging.getLogger().handlers:
    _handler.addFilter(RequestIdFilter())


def _unauthenticated_local_dev_allowed() -> bool:
    return os.getenv("ALLOW_UNAUTHENTICATED_LOCAL_DEV", "").strip().lower() == "true"


def _error_response(request: Request, status_code: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}, "request_id": request.state.request_id}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def _build_graph() -> tuple[object, sqlite3.Connection]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    db_path = Path(os.getenv("CHECKPOINT_DB_PATH", "data/conversations.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), check_same_thread=False, timeout=10)
    try:
        return DoctorAppointmentAgent().workflow(checkpointer=SqliteSaver(connection)), connection
    except Exception:
        connection.close()
        raise


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.graph = None
        app.state.checkpoint_connection = None
        app.state.startup_error = None
        try:
            app.state.graph, app.state.checkpoint_connection = _build_graph()
            logger.info("Application dependencies initialized")
        except Exception as exc:
            # Do not expose secret-bearing provider/configuration details to clients.
            app.state.startup_error = type(exc).__name__
            logger.error("Application started without an available graph: %s", type(exc).__name__)
        yield
        if app.state.checkpoint_connection is not None:
            app.state.checkpoint_connection.close()

    api = FastAPI(title="Clinic AI Customer Service", lifespan=lifespan)
    api.state.invoke_lock = threading.Lock()

    @api.middleware("http")
    async def add_request_context(request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = incoming_id if _REQUEST_ID_PATTERN.fullmatch(incoming_id) else str(uuid4())

        auth_error = None
        if request.url.path == "/execute" and request.method.upper() == "POST":
            configured_token = os.getenv("API_ACCESS_TOKEN", "").strip()
            supplied_token = request.headers.get("X-API-Key", "")
            if not configured_token:
                if not _unauthenticated_local_dev_allowed():
                    auth_error = _error_response(
                        request, 503, "api_auth_not_configured",
                        "API access is not configured. Set API_ACCESS_TOKEN before accepting requests.",
                    )
            elif not supplied_token or not hmac.compare_digest(configured_token, supplied_token):
                auth_error = _error_response(request, 401, "unauthorized", "Valid API credentials are required.")

        if auth_error is not None:
            response = auth_error
        else:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("Unhandled application error", extra={"request_id": request.state.request_id})
                response = _error_response(request, 500, "internal_error", "The request could not be processed.")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Request validation failed on %s", request.url.path, extra={"request_id": request.state.request_id})
        # Exclude Pydantic's raw input/context fields so patient-provided data is not echoed.
        safe_details = [
            {"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")}
            for error in exc.errors()
        ]
        return _error_response(request, 422, "validation_error", "Invalid request", safe_details)

    @api.get("/health/live")
    def health_live(request: Request):
        return {"status": "alive", "request_id": request.state.request_id}

    @api.get("/health")
    @api.get("/health/ready")
    def health(request: Request):
        if request.app.state.graph is None:
            return _error_response(request, 503, "service_unavailable", "Service dependencies are unavailable.")
        if not os.getenv("API_ACCESS_TOKEN", "").strip() and not _unauthenticated_local_dev_allowed():
            return _error_response(request, 503, "api_auth_not_configured", "API access is not configured.")
        return {
            "status": "ok",
            "api_auth": "enabled" if os.getenv("API_ACCESS_TOKEN", "").strip() else "local-dev-only",
            "request_id": request.state.request_id,
        }

    @api.post("/execute")
    def execute_agent(user_input: UserQuery, request: Request):
        graph = request.app.state.graph
        if graph is None:
            logger.error("Agent request rejected because graph is unavailable", extra={"request_id": request.state.request_id})
            return _error_response(request, 503, "service_unavailable", "Service dependencies are unavailable.")
        session_id = user_input.session_id or str(uuid4())
        try:
            # SqliteSaver shares one connection in this single-process prototype; serialize graph
            # invocations until the checkpointer is moved to a concurrency-safe deployment store.
            with request.app.state.invoke_lock:
                response = graph.invoke(
                    {
                        "messages": [HumanMessage(content=user_input.messages)],
                        "id_number": user_input.id_number,
                        "next": "",
                        "query": "",
                        "current_reasoning": "",
                        "escalation_case_id": "",
                        "escalation_status": "",
                        "escalation_trigger": "",
                    },
                    config={"recursion_limit": 20, "configurable": {"thread_id": make_thread_id(user_input.id_number, session_id)}},
                )
            messages = [
                {"type": getattr(message, "type", "message"), "content": message.content}
                for message in response.get("messages", [])
            ]
        except Exception:
            logger.exception("Agent execution failed", extra={"request_id": request.state.request_id})
            return _error_response(request, 500, "agent_execution_failed", "The request could not be processed.")
        logger.info("Agent request completed", extra={"request_id": request.state.request_id})
        result_body = {"session_id": session_id, "messages": messages, "request_id": request.state.request_id}
        escalation_status = response.get("escalation_status")
        if escalation_status:
            result_body["escalation"] = {
                "status": escalation_status,
                "case_id": response.get("escalation_case_id") or "",
                "trigger": response.get("escalation_trigger") or "",
            }
        return result_body

    return api


app = create_app()
