from langchain_core.messages import AIMessage, HumanMessage

import agent as agent_module
from agent import DoctorAppointmentAgent


class FakeStructuredLLM:
    def __init__(self, intent):
        self.intent = intent

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return {"intent": self.intent, "reasoning": "test route"}


class RecordingWorker:
    def __init__(self, **kwargs):
        self.tools = kwargs["tools"]
        self.prompt = kwargs["prompt"]
        self.calls = []

    def invoke(self, state):
        self.calls.append(state)
        return {"messages": [AIMessage(content="Tool outcome: no mutation was performed.")]}


def test_booking_workflow_exposes_availability_and_mutation_tools(monkeypatch):
    workers = []

    def build_worker(**kwargs):
        worker = RecordingWorker(**kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(agent_module, "create_react_agent", build_worker)
    graph = DoctorAppointmentAgent(llm_model=FakeStructuredLLM("book")).workflow()
    result = graph.invoke({
        "id_number": 1234567,
        "messages": [HumanMessage(content="Book with Dr Smith on 12-10-2026 at 10:00 am")],
        "thread_ref": "unit-test-thread",
    })

    assert len(workers) == 1
    assert {tool.name for tool in workers[0].tools} == {
        "check_availability_by_doctor", "check_availability_by_specialization",
        "prepare_appointment_change",
    }
    assert "thread_ref" in result
    prompt = workers[0].prompt.messages[0].prompt.template
    assert "separate, exact YES" in prompt
    assert "The API alone executes" in prompt
    assert result["messages"][-1].content == "Tool outcome: no mutation was performed."
    assert result["messages"][-1].name == "booking_node"


def test_cancel_and_reschedule_intents_reach_booking_specialist(monkeypatch):
    routed = []

    class Worker:
        def invoke(self, state):
            routed.append(state["query"])
            return {"messages": [AIMessage(content="Please confirm the requested change.")]}

    monkeypatch.setattr(agent_module, "create_react_agent", lambda **_kwargs: Worker())
    for intent, query in [
        ("cancel", "Cancel with Dr Smith on 12-10-2026 at 10:00 am"),
        ("reschedule", "Reschedule with Dr Smith from 12-10-2026 at 10:00 am to 13-10-2026 at 11:00 am"),
    ]:
        graph = DoctorAppointmentAgent(llm_model=FakeStructuredLLM(intent)).workflow()
        result = graph.invoke({"id_number": 1234567, "messages": [HumanMessage(content=query)]})
        assert result["messages"][-1].name == "booking_node"
    assert routed == [
        "Cancel with Dr Smith on 12-10-2026 at 10:00 am",
        "Reschedule with Dr Smith from 12-10-2026 at 10:00 am to 13-10-2026 at 11:00 am",
    ]
