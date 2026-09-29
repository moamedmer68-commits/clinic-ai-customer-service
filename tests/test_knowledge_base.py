import json

from knowledge_base import load_faq, retrieve_faq


def test_retrieves_supported_faq_with_keywords():
    entries = [{"id": "hours", "question": "Clinic opening hours", "keywords": ["open", "schedule"], "answer": "Approved hours."}]
    match = retrieve_faq("When are you open?", entries)
    assert match is not None
    assert match.answer == "Approved hours."
    assert match.source_id == "hours"


def test_rejects_low_evidence_and_empty_queries():
    entries = [{"question": "Clinic opening hours", "keywords": ["schedule"], "answer": "Hours."}]
    assert retrieve_faq("insurance policy", entries) is None
    assert retrieve_faq("???", entries) is None


def test_loader_fails_closed_and_filters_invalid_records(tmp_path):
    path = tmp_path / "faq.json"
    path.write_text(json.dumps([{"question": "Q", "answer": "A"}, {"question": "bad"}, 4]), encoding="utf-8")
    assert len(load_faq(path)) == 1
    assert load_faq(tmp_path / "missing.json") == []


def test_faq_node_uses_retrieval_and_unknown_fallback(tmp_path, monkeypatch):
    import agent as agent_module
    from agent import DoctorAppointmentAgent

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clinic_faq.json").write_text(json.dumps([
        {"question": "Clinic opening hours", "keywords": ["open", "hours"], "answer": "Verified hours."}
    ]), encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    service = DoctorAppointmentAgent(llm_model=object())
    answer = service.faq_node({"query": "When are you open?", "messages": []}).update["messages"][0].content
    assert answer == "Verified hours."
    unknown = service.faq_node({"query": "Insurance coverage?", "messages": []}).update["messages"][0].content
    assert "don’t have a verified answer" in unknown
