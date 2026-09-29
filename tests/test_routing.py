from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END

import agent as agent_module
from agent import DoctorAppointmentAgent


class FakeStructuredLLM:
    def __init__(self, intent):
        self.intent = intent
        self.requests = []

    def with_structured_output(self, _schema):
        return self

    def invoke(self, messages):
        self.requests.append(messages)
        return {"intent": self.intent, "reasoning": "deterministic test route"}


def test_supervisor_routes_using_latest_human_message_in_history():
    llm = FakeStructuredLLM("availability")
    service = DoctorAppointmentAgent(llm_model=llm)

    command = service.supervisor_node({
        "id_number": 1234567,
        "messages": [
            HumanMessage(content="What are your opening hours?"),
            AIMessage(content="We are open weekdays.", name="information_node"),
            HumanMessage(content="Is Dr Smith available on 12-10-2026 at 10:00?"),
        ],
    })

    assert command.goto == "information_node"
    assert command.update["query"] == "Is Dr Smith available on 12-10-2026 at 10:00?"


def test_incomplete_booking_is_clarified_without_dispatching_booking_agent():
    service = DoctorAppointmentAgent(llm_model=FakeStructuredLLM("book"))

    command = service.supervisor_node({
        "id_number": 1234567,
        "messages": [HumanMessage(content="Please book an appointment.")],
    })

    assert command.goto == END
    assert command.update["next"] == END
    assert "doctor" in command.update["messages"][0].content.lower()
    assert "date and time" in command.update["messages"][0].content.lower()


def test_unsupported_request_uses_fallback_clarification():
    service = DoctorAppointmentAgent(llm_model=FakeStructuredLLM("fallback"))

    command = service.supervisor_node({
        "id_number": 1234567,
        "messages": [HumanMessage(content="Can you give me legal advice?")],
    })

    assert command.goto == END
    assert "availability" in command.update["messages"][0].content.lower()


def test_graph_stops_after_one_worker_response(monkeypatch):
    worker_calls = []

    class FakeWorker:
        def invoke(self, state):
            worker_calls.append(state["query"])
            return {"messages": [AIMessage(content="Booked response")]}

    monkeypatch.setattr(agent_module, "create_react_agent", lambda **_kwargs: FakeWorker())
    service = DoctorAppointmentAgent(llm_model=FakeStructuredLLM("book"))
    graph = service.workflow()

    result = graph.invoke({
        "id_number": 1234567,
        "messages": [HumanMessage(content="Book with Dr Smith on 12-10-2026 at 10:00 am.")],
    })

    assert worker_calls == ["Book with Dr Smith on 12-10-2026 at 10:00 am."]
    assert result["messages"][-1].name == "booking_node"
