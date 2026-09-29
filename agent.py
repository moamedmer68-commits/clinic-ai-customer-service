import logging
import re
from typing import Any, Literal
from langgraph.types import Command
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, HumanMessage
from prompt_library.prompt import system_prompt
from utils.llms import LLMModel
from toolkit.toolkits import *

logger = logging.getLogger(__name__)

class Router(TypedDict):
    """The supervisor's semantic classification of the latest patient request."""

    intent: Literal["faq", "availability", "book", "cancel", "reschedule", "fallback"]
    reasoning: str

class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    id_number: int
    next: str
    query: str
    current_reasoning: str
    intent: str


INTENT_DESTINATIONS = {
    "faq": "information_node",
    "availability": "information_node",
    "book": "booking_node",
    "cancel": "booking_node",
    "reschedule": "booking_node",
}

FALLBACK_CLARIFICATION = (
    "I can help with clinic FAQs, doctor availability, and booking, cancelling, or "
    "rescheduling an appointment. Which of those would you like to do?"
)


def _clarification_for_incomplete_appointment(intent: str, query: str) -> str | None:
    """Prevent incomplete appointment requests from reaching mutation-capable agents."""
    if intent not in {"book", "cancel", "reschedule"}:
        return None

    normalized = query.lower()
    has_provider = bool(re.search(r"\b(?:dr\.?|doctor|specialist)\s+\w+|\bwith\s+\w+", normalized))
    date_references = re.findall(
        r"\b(?:today|tomorrow|next\s+\w+|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\b\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?\b",
        normalized,
    )
    time_references = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b", normalized)

    if intent == "reschedule":
        if not has_provider or len(date_references) < 2 or len(time_references) < 2:
            return "To reschedule, please provide the doctor, your current appointment date and time, and the new date and time."
    elif not has_provider or not date_references or not time_references:
        action = "cancel" if intent == "cancel" else "book"
        return f"To {action} an appointment, please provide the doctor (or specialty) and the appointment date and time."
    return None


def _latest_human_query(messages: list[Any]) -> str:
    """Return the newest patient message from a persisted LangGraph history."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = message.content
        elif isinstance(message, dict) and message.get("role") in {"user", "human"}:
            content = message.get("content", "")
        elif getattr(message, "type", None) in {"human", "user"}:
            content = getattr(message, "content", "")
        else:
            continue
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _last_message_is_worker_response(messages: list[Any]) -> bool:
    if not messages:
        return False
    last_message = messages[-1]
    return isinstance(last_message, AIMessage) and getattr(last_message, "name", None) in INTENT_DESTINATIONS.values()

class DoctorAppointmentAgent:
    def __init__(self, llm_model=None):
        self.llm_model = llm_model or LLMModel().get_model()
    
    def supervisor_node(self, state: AgentState) -> Command[Literal['information_node', 'booking_node', '__end__']]:
        logger.debug("Supervisor evaluating request")
        
        # Each worker response returns here. End that execution rather than allowing
        # the supervisor to invoke the same worker repeatedly. A subsequent human
        # message in the persisted thread starts a new routing decision.
        if _last_message_is_worker_response(state["messages"]):
            return Command(goto=END, update={"next": END})

        query = _latest_human_query(state["messages"])
        if not query:
            return Command(
                goto=END,
                update={
                    "next": END,
                    "intent": "fallback",
                    "current_reasoning": "No patient request was available to route.",
                    "messages": [AIMessage(content=FALLBACK_CLARIFICATION, name="supervisor")],
                },
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"user's identification number is {state['id_number']}"},
        ] + state["messages"]

        response = self.llm_model.with_structured_output(Router).invoke(messages)
        intent = response["intent"]
        reasoning = response["reasoning"]
        goto = INTENT_DESTINATIONS.get(intent)
        logger.info("Supervisor classified request as %s", intent)

        update = {
            "intent": intent,
            "query": query,
            "current_reasoning": reasoning,
        }
        clarification = _clarification_for_incomplete_appointment(intent, query)
        if clarification:
            logger.info("Supervisor requested appointment details before routing")
            update.update({
                "next": END,
                "messages": [AIMessage(content=clarification, name="supervisor")],
            })
            return Command(goto=END, update=update)
        if goto is None:
            update.update({
                "next": END,
                "messages": [AIMessage(content=FALLBACK_CLARIFICATION, name="supervisor")],
            })
            return Command(goto=END, update=update)

        update["next"] = goto
        return Command(goto=goto, update=update)

    def information_node(self, state: AgentState) -> Command[Literal['supervisor']]:
        logger.info("Information agent invoked")
    
        system_prompt = f"You are specialized agent to provide information related to availability of doctors or any FAQs related to hospital based on the query. You have access to the tool.\n Make sure to ask user politely if you need any further information to execute the tool.\n Do not assume a year: use the date supplied by the patient, and ask for a complete date when it is needed but missing.\n The user's identification number is {state['id_number']}."
        
        system_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        system_prompt
                    ),
                    (
                        "placeholder", 
                        "{messages}"
                    ),
                ]
            )
        
        information_agent = create_react_agent(model=self.llm_model,tools=[check_availability_by_doctor,check_availability_by_specialization] ,prompt=system_prompt)
        
        result = information_agent.invoke(state)
        
        return Command(
            update={
                "messages": [
                    AIMessage(content=result["messages"][-1].content, name="information_node")
                ]
            },
            goto="supervisor",
        )

    def booking_node(self, state: AgentState) -> Command[Literal['supervisor']]:
        logger.info("Booking agent invoked")
    
        system_prompt = f"You are specialized agent to set, cancel or reschedule appointment based on the query. You have access to the tool.\n Make sure to ask user politely if you need any further information to execute the tool.\n Do not assume a year: use the date supplied by the patient, and ask for a complete date and time when either is needed but missing.\n The user's identification number is {state['id_number']}."
        
        system_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        system_prompt
                    ),
                    (
                        "placeholder", 
                        "{messages}"
                    ),
                ]
            )
        booking_agent = create_react_agent(model=self.llm_model,tools=[set_appointment,cancel_appointment,reschedule_appointment],prompt=system_prompt)

        result = booking_agent.invoke(state)
        
        return Command(
            update={
                "messages": [
                    AIMessage(content=result["messages"][-1].content, name="booking_node")
                ]
            },
            goto="supervisor",
        )

    def workflow(self, checkpointer=None):
        self.graph = StateGraph(AgentState)
        self.graph.add_node("supervisor", self.supervisor_node)
        self.graph.add_node("information_node", self.information_node)
        self.graph.add_node("booking_node", self.booking_node)
        self.graph.add_edge(START, "supervisor")
        self.app = self.graph.compile(checkpointer=checkpointer)
        return self.app
