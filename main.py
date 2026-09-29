import logging
import os
import sqlite3
from uuid import uuid4
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage

from agent import DoctorAppointmentAgent
from utils.session import make_thread_id

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

class UserQuery(BaseModel):
    id_number: int = Field(..., ge=1000000, le=99999999)
    messages: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)

# Keep the SQLite connection and checkpointer alive for the application lifetime.
DB_PATH = Path(os.getenv("CHECKPOINT_DB_PATH", "data/conversations.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
checkpoint_connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
checkpointer = SqliteSaver(checkpoint_connection)
agent = DoctorAppointmentAgent()
app_graph = agent.workflow(checkpointer=checkpointer)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Request validation failed for %s", request.url.path)
    return JSONResponse(status_code=422, content={"error": "Invalid request", "details": exc.errors()})

@app.exception_handler(Exception)
async def application_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "The request could not be processed."})

@app.post("/execute")
def execute_agent(user_input: UserQuery):
    logger.info("Processing agent request")
    session_id = user_input.session_id or str(uuid4())
    thread_id = make_thread_id(user_input.id_number, session_id)
    query_data = {
        "messages": [HumanMessage(content=user_input.messages)],
        "id_number": user_input.id_number,
        "next": "",
        "query": "",
        "current_reasoning": "",
    }
    response = app_graph.invoke(
        query_data,
        config={"recursion_limit": 20, "configurable": {"thread_id": thread_id}},
    )
    messages = [
        {"type": getattr(message, "type", "message"), "content": message.content}
        for message in response.get("messages", [])
    ]
    return {"session_id": session_id, "messages": messages}
