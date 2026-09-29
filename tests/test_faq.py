import json

from langchain_core.messages import HumanMessage

import agent as agent_module
from agent import DoctorAppointmentAgent


class UnusedLLM:
    pass


def test_faq_answers_from_configured_source_and_supports_paraphrase(tmp_path, monkeypatch):
    faq_dir = tmp_path / "data"
    faq_dir.mkdir()
    faq_file = faq_dir / "clinic_faq.json"
    faq_file.write_text(json.dumps([{
        "question": "What are the clinic opening hours?",
        "keywords": ["hours", "open", "opening", "schedule"],
        "answer": "The clinic is open Monday through Friday, 9 AM to 5 PM.",
    }]), encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    service = DoctorAppointmentAgent(llm_model=UnusedLLM())

    result = service.faq_node({"query": "When is the clinic open?", "messages": []})

    assert "Monday through Friday" in result.update["messages"][0].content
    assert result.update["messages"][0].name == "faq_node"


def test_faq_unknown_answer_does_not_invent_policy(tmp_path, monkeypatch):
    faq_dir = tmp_path / "data"
    faq_dir.mkdir()
    (faq_dir / "clinic_faq.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    service = DoctorAppointmentAgent(llm_model=UnusedLLM())

    result = service.faq_node({"query": "Do you accept my insurance?", "messages": []})

    assert "don’t have a verified answer" in result.update["messages"][0].content


def test_faq_refuses_medical_advice_requests(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clinic_faq.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    service = DoctorAppointmentAgent(llm_model=UnusedLLM())

    result = service.faq_node({"query": "What medicine should I take for tooth pain?", "messages": []})

    assert "can’t diagnose" in result.update["messages"][0].content
    assert "treatment" in result.update["messages"][0].content


def test_faq_intent_routes_to_dedicated_faq_node():
    from tests.test_routing import FakeStructuredLLM

    service = DoctorAppointmentAgent(llm_model=FakeStructuredLLM("faq"))
    command = service.supervisor_node({
        "id_number": 1234567,
        "messages": [HumanMessage(content="What are your opening hours?")],
    })

    assert command.goto == "faq_node"
    assert command.update["next"] == "faq_node"
