import json
import logging
import re
from pathlib import Path
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
    "faq": "faq_node",
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
    return isinstance(last_message, AIMessage) and getattr(last_message, "name", None) in {"faq_node", "information_node", "booking_node"}

class DoctorAppointmentAgent:
    def __init__(self, llm_model=None):
        self.llm_model = llm_model or LLMModel().get_model()
    
    def supervisor_node(self, state: AgentState) -> Command[Literal['faq_node', 'information_node', 'booking_node', '__end__']]:
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

    def faq_node(self, state: AgentState) -> Command[Literal["supervisor"]]:
        """Answer clinic FAQs only when supported by configured clinic content."""
        query = (state.get("query") or _latest_human_query(state.get("messages", []))).strip()
        normalized = query.casefold()
        medical_terms = {"diagnose", "diagnosis", "symptom", "symptoms", "pain", "swollen", "bleeding", "infection", "medicine", "medication", "dosage", "treatment"}
        query_terms = set(re.findall(r"[a-z0-9]+", normalized))
        if query_terms & medical_terms:
            answer = ("I can share clinic service information, but I can’t diagnose symptoms or recommend "
                      "treatment. Please contact a qualified healthcare professional for medical advice.")
        else:
            faq_path = Path(__file__).resolve().parent / "data" / "clinic_faq.json"
            try:
                entries = json.loads(faq_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.exception("Unable to load clinic FAQ content")
                entries = []
            best_entry = None
            best_score = 0
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict) or not isinstance(entry.get("answer"), str):
                    continue
                terms = set()
                for field in ("question", "keywords"):
                    value = entry.get(field, "")
                    if isinstance(value, str):
                        terms.update(re.findall(r"[a-z0-9]+", value.casefold()))
                    elif isinstance(value, list):
                        terms.update(token for item in value if isinstance(item, str)
                                     for token in re.findall(r"[a-z0-9]+", item.casefold()))
                score = len(query_terms & terms)
                if score > best_score:
                    best_entry, best_score = entry, score
            answer = best_entry["answer"].strip() if best_entry and best_entry["answer"].strip() else (
                "I don’t have a verified answer to that clinic question yet. Please contact the clinic directly "
                "or ask about doctor availability or appointment booking."
            )
        return Command(update={"messages": [AIMessage(content=answer, name="faq_node")]}, goto="supervisor")

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
    
        system_prompt = f"""You are the clinic appointment specialist. Use only the supplied appointment tools.
Required information: exact doctor name, complete date and time, and patient ID (provided by the application).
Ask a clarification question before calling a tool if any required detail is missing or ambiguous. Never infer a year.
Before booking, cancelling, or rescheduling, clearly state the exact action and appointment details and ask the patient to confirm.
Do not call a mutation tool until the patient has explicitly confirmed that exact action/details in the conversation.
After a tool call, report its actual result faithfully. Claim success only when the tool returns its explicit success result; explain unavailable slots, unmatched appointments, and data-service errors without claiming a change.
Never expose the patient's ID in the response. The patient's ID supplied by the application is {state['id_number']}."""
        
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
        booking_agent = create_react_agent(model=self.llm_model,tools=[check_availability_by_doctor, check_availability_by_specialization, set_appointment,cancel_appointment,reschedule_appointment],prompt=system_prompt)

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
        self.graph.add_node("faq_node", self.faq_node)
        self.graph.add_node("information_node", self.information_node)
        self.graph.add_node("booking_node", self.booking_node)
        self.graph.add_edge(START, "supervisor")
        self.app = self.graph.compile(checkpointer=checkpointer)
        return self.app
