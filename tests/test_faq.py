import json

from langchain_core.messages import HumanMessage

from knowledge_base import FAQMatch
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
    monkeypatch.setattr(
        agent_module,
        "retrieve_semantic_faq",
        lambda query, **kwargs: FAQMatch(
            answer="The clinic is open Monday through Friday, 9 AM to 5 PM.",
            question="What are the clinic opening hours?",
            score=0.91,
            source_id="clinic-hours",
        ),
    )
    service = DoctorAppointmentAgent(llm_model=UnusedLLM())

    result = service.faq_node({"query": "When is the clinic open?", "messages": []})

    assert "Monday through Friday" in result.update["messages"][0].content
    assert result.update["messages"][0].name == "faq_node"


def test_faq_unknown_answer_does_not_invent_policy(tmp_path, monkeypatch):
    faq_dir = tmp_path / "data"
    faq_dir.mkdir()
    (faq_dir / "clinic_faq.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "handoffs.sqlite3"))
    service = DoctorAppointmentAgent(llm_model=UnusedLLM())

    result = service.faq_node({"query": "Do you accept my insurance?", "messages": []})

    assert "I’ve escalated this request" in result.update["messages"][0].content
    assert "pending human review" in result.update["messages"][0].content
    assert result.update["escalation_status"] == "pending"


def test_faq_refuses_medical_advice_requests(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clinic_faq.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "handoffs.sqlite3"))
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


def test_faq_node_honors_clinic_faq_path_for_local_demo(tmp_path, monkeypatch):
    configured_path = tmp_path / "synthetic" / "clinic_faq.json"
    monkeypatch.setenv("CLINIC_FAQ_PATH", str(configured_path))
    monkeypatch.setenv("FAQ_RAG_INDEX_PATH", str(tmp_path / "synthetic" / "faq_index"))
    captured = {}

    def fake_retrieve(query, **kwargs):
        captured.update(kwargs)
        return FAQMatch(
            answer="DEMO ONLY — FAKE DATA, NOT CLINIC-APPROVED: Synthetic answer.",
            question="A synthetic demo question?",
            score=0.99,
            source_id="demo-test",
        )

    monkeypatch.setattr(agent_module, "retrieve_semantic_faq", fake_retrieve)
    service = DoctorAppointmentAgent(llm_model=UnusedLLM())
    result = service.faq_node({"query": "A synthetic demo question?", "messages": []})

    assert captured["source_path"] == configured_path
    assert captured["index_dir"] == tmp_path / "synthetic" / "faq_index"
    assert "DEMO ONLY" in result.update["messages"][0].content
    assert "Source: demo-test" in result.update["messages"][0].content
