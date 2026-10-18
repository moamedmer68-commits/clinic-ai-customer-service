import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agent as agent_module
from agent import DoctorAppointmentAgent
from support.handoff import (
    build_handoff_summary,
    create_handoff_case,
    detect_escalation_trigger,
    get_handoff_case,
    list_pending_handoffs,
    update_handoff_status,
)


def test_handoff_trigger_detection():
    assert detect_escalation_trigger("I want to speak to a human representative.") == "human_requested"
    assert detect_escalation_trigger("I need to file a formal complaint.") == "complaint_requested"
    assert detect_escalation_trigger("I have severe bleeding and need help.") == "sensitive_medical_request"
    assert detect_escalation_trigger("What are your opening hours?") is None


def test_handoff_summary_redacts_identifiers_and_bounds_content():
    summary = build_handoff_summary(
        [
            HumanMessage(content="My patient ID is 1234567 and email is test@example.com."),
            AIMessage(content="How can I help?"),
            HumanMessage(content="A" * 1000),
        ]
    )
    assert "1234567" not in summary
    assert "test@example.com" not in summary
    assert "[REDACTED_ID]" in summary
    assert "[REDACTED_EMAIL]" in summary
    assert "..." in summary


def test_handoff_case_lifecycle(tmp_path):
    db_path = tmp_path / "handoffs.sqlite3"
    messages = [HumanMessage(content="Please connect me to a human."), AIMessage(content="I can help.")]
    case = create_handoff_case(messages, "human_requested", db_path=db_path)

    assert case["status"] == "pending"
    stored = get_handoff_case(case["case_id"], db_path=db_path)
    assert stored is not None
    assert stored["trigger"] == "human_requested"
    assert stored["status"] == "pending"

    pending = list_pending_handoffs(db_path=db_path)
    assert [item["case_id"] for item in pending] == [case["case_id"]]

    assert update_handoff_status(case["case_id"], "acknowledged", db_path=db_path)
    assert get_handoff_case(case["case_id"], db_path=db_path)["status"] == "acknowledged"

    assert update_handoff_status(case["case_id"], "resolved", db_path=db_path)
    assert list_pending_handoffs(db_path=db_path) == []


def test_invalid_handoff_status_is_rejected(tmp_path):
    db_path = tmp_path / "handoffs.sqlite3"
    case = create_handoff_case([HumanMessage(content="help")], "human_requested", db_path=db_path)
    with pytest.raises(ValueError):
        update_handoff_status(case["case_id"], "unknown", db_path=db_path)


def test_supervisor_escalates_explicit_human_request_without_llm(monkeypatch, tmp_path):
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "handoffs.sqlite3"))

    class ExplodingLLM:
        def with_structured_output(self, _schema):
            raise AssertionError("LLM should not be called for an explicit escalation request")

    service = DoctorAppointmentAgent(llm_model=ExplodingLLM())
    command = service.supervisor_node(
        {
            "id_number": 1234567,
            "messages": [HumanMessage(content="Please connect me to a human representative.")],
        }
    )

    assert command.goto == "__end__"
    assert command.update["intent"] == "escalation"
    assert command.update["escalation_status"] == "pending"
    message = command.update["messages"][0]
    assert message.name == "escalation_node"
    assert "pending human review" in message.content
    assert "human response yet" in message.content


def test_faq_unresolved_creates_handoff(monkeypatch, tmp_path):
    db_path = tmp_path / "handoffs.sqlite3"
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))
    monkeypatch.setattr(agent_module, "retrieve_semantic_faq", lambda *args, **kwargs: None)

    service = DoctorAppointmentAgent(llm_model=object())
    command = service.faq_node(
        {
            "id_number": 1234567,
            "messages": [HumanMessage(content="Do you accept my specific insurance plan?")],
            "query": "Do you accept my specific insurance plan?",
            "next": "",
            "current_reasoning": "",
            "intent": "faq",
        }
    )

    message = command.update["messages"][0]
    assert message.name == "escalation_node"
    assert command.update["escalation_status"] == "pending"
    assert "case ID" in message.content
    assert get_handoff_case(command.update["escalation_case_id"], db_path=db_path)["trigger"] == "unresolved_faq"


def test_handoff_is_truthful_when_queue_persistence_fails(monkeypatch):
    monkeypatch.setattr(agent_module, "_escalate", lambda *_args, **_kwargs: (None, agent_module.format_handoff_failure()))
    service = DoctorAppointmentAgent(llm_model=object())
    command = service.supervisor_node(
        {
            "id_number": 1234567,
            "messages": [HumanMessage(content="Please connect me to a human representative.")],
        }
    )
    message = command.update["messages"][0]
    assert command.update["escalation_status"] == "failed"
    assert "No human has been contacted" in message.content


def test_faq_retrieval_error_creates_handoff(monkeypatch, tmp_path):
    db_path = tmp_path / "handoffs.sqlite3"
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))

    def raise_error(*args, **kwargs):
        raise RuntimeError("retrieval failed")

    monkeypatch.setattr(agent_module, "retrieve_semantic_faq", raise_error)

    service = DoctorAppointmentAgent(llm_model=object())
    command = service.faq_node(
        {
            "id_number": 1234567,
            "messages": [HumanMessage(content="What services do you offer?")],
            "query": "What services do you offer?",
            "next": "",
            "current_reasoning": "",
            "intent": "faq",
        }
    )

    assert command.update["escalation_status"] == "pending"
    assert get_handoff_case(command.update["escalation_case_id"], db_path=db_path)["trigger"] == "faq_retrieval_error"
