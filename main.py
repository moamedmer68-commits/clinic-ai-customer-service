import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from agent import DoctorAppointmentAgent

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

class UserQuery(BaseModel):
    id_number: int = Field(..., ge=1000000, le=99999999)
    messages: str = Field(..., min_length=1)

agent = DoctorAppointmentAgent()
app_graph = agent.workflow()

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
    query_data = {
        "messages": [HumanMessage(content=user_input.messages)],
        "id_number": user_input.id_number,
        "next": "",
        "query": "",
        "current_reasoning": "",
    }
    response = app_graph.invoke(query_data, config={"recursion_limit": 20})
    return {"messages": response["messages"]}
