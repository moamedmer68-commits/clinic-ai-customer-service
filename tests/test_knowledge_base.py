import json
import math
from pathlib import Path

import agent as agent_module
from agent import DoctorAppointmentAgent
from knowledge_base import (
    FAQMatch,
    build_semantic_index,
    evaluate_retrieval,
    load_faq,
    load_or_build_faq_index,
    retrieve_faq,
    retrieve_semantic_faq,
)


class FakeEmbeddings:
    """Deterministic test-only embeddings with semantic topic buckets."""

    topics = {
        "open": 0,
        "opening": 0,
        "hours": 0,
        "schedule": 0,
        "visit": 0,
        "insurance": 1,
        "coverage": 1,
        "plans": 1,
        "cancel": 2,
        "cancellation": 2,
        "appointment": 2,
    }

    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0

    @staticmethod
    def _embed(text):
        vector = [0.0, 0.0, 0.0, 0.0]
        for token in text.casefold().split():
            token = token.strip(".,?!")
            if token in FakeEmbeddings.topics:
                vector[FakeEmbeddings.topics[token]] += 1.0
        if not any(vector):
            vector[3] = 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]

    def embed_documents(self, texts):
        self.document_calls += 1
        return [self._embed(text) for text in texts]

    def embed_query(self, text):
        self.query_calls += 1
        return self._embed(text)


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
    assert retrieve_faq("what is the and are", entries) is None


def test_loader_fails_closed_filters_invalid_records_and_normalizes_metadata(tmp_path):
    path = tmp_path / "faq.json"
    path.write_text(json.dumps([
        {
            "id": 42,
            "question": " Q ",
            "answer": " A ",
            "keywords": [" alpha ", "", 3],
            "source": {"title": " Approved guide ", "ignored": "value"},
        },
        {"question": "bad"},
        {"question": " ", "answer": "A"},
        4,
    ]), encoding="utf-8")
    assert load_faq(path) == [{
        "id": "42",
        "question": "Q",
        "answer": "A",
        "keywords": ["alpha"],
        "source": {"title": "Approved guide"},
    }]
    assert load_faq(tmp_path / "missing.json") == []


def test_semantic_retrieval_handles_paraphrase_and_source_metadata():
    entries = [
        {
            "id": "clinic-hours",
            "question": "What are the clinic opening hours?",
            "keywords": ["open", "schedule"],
            "answer": "Approved hours.",
            "source": {"title": "Synthetic FAQ"},
        },
        {
            "id": "insurance",
            "question": "Which insurance plans are accepted?",
            "keywords": ["insurance", "coverage"],
            "answer": "Approved insurance.",
        },
    ]
    embeddings = FakeEmbeddings()
    index = build_semantic_index(entries, embedding_model=embeddings, model_name="fake-v1")
    match = retrieve_semantic_faq(
        "When can I visit the clinic?",
        index=index,
        embedding_model=embeddings,
        min_score=0.70,
    )
    assert match is not None
    assert match.source_id == "clinic-hours"
    assert match.source == {"title": "Synthetic FAQ"}


def test_semantic_retrieval_has_safe_no_answer_threshold_and_source_filter():
    entries = [
        {"id": "hours", "question": "Clinic opening hours", "keywords": ["open"], "answer": "Hours."},
        {"id": "insurance", "question": "Accepted insurance plans", "keywords": ["coverage"], "answer": "Insurance."},
    ]
    embeddings = FakeEmbeddings()
    index = build_semantic_index(entries, embedding_model=embeddings, model_name="fake-v1")
    assert retrieve_semantic_faq(
        "unrelated pediatric orthodontics",
        index=index,
        embedding_model=embeddings,
        min_score=0.90,
    ) is None
    assert retrieve_semantic_faq(
        "When is it open?",
        index=index,
        embedding_model=embeddings,
        source_ids={"insurance"},
        min_score=0.50,
    ) is None


def test_semantic_index_persists_and_rebuilds_when_content_changes(tmp_path):
    source = tmp_path / "faq.json"
    source.write_text(json.dumps([
        {"id": "hours", "question": "Clinic opening hours", "keywords": ["open"], "answer": "Hours."},
    ]), encoding="utf-8")
    index_dir = tmp_path / "index"
    first_embeddings = FakeEmbeddings()
    first = load_or_build_faq_index(source, index_dir, embedding_model=first_embeddings, model_name="fake-v1")
    assert first_embeddings.document_calls == 1
    assert (index_dir / "metadata.json").exists()
    assert (index_dir / "embeddings.npy").exists()

    second_embeddings = FakeEmbeddings()
    second = load_or_build_faq_index(source, index_dir, embedding_model=second_embeddings, model_name="fake-v1")
    assert second.content_hash == first.content_hash
    assert second_embeddings.document_calls == 0

    source.write_text(json.dumps([
        {"id": "hours", "question": "Clinic opening hours", "keywords": ["open"], "answer": "Updated hours."},
    ]), encoding="utf-8")
    third_embeddings = FakeEmbeddings()
    rebuilt = load_or_build_faq_index(source, index_dir, embedding_model=third_embeddings, model_name="fake-v1")
    assert rebuilt.content_hash != first.content_hash
    assert third_embeddings.document_calls == 1


def test_retrieval_evaluation_reports_hit_rate_mrr_and_no_answer_rate():
    entries = [
        {"id": "clinic-hours", "question": "Clinic opening hours", "keywords": ["open"], "answer": "Hours."},
        {"id": "insurance", "question": "Accepted insurance plans", "keywords": ["coverage"], "answer": "Insurance."},
        {"id": "cancellation", "question": "How to cancel an appointment", "keywords": ["cancel"], "answer": "Cancel."},
    ]
    embeddings = FakeEmbeddings()
    index = build_semantic_index(entries, embedding_model=embeddings, model_name="fake-v1")
    evaluation_cases = json.loads(
        (Path(__file__).parent / "fixtures" / "faq_retrieval_eval.json").read_text(encoding="utf-8")
    )
    metrics = evaluate_retrieval(
        evaluation_cases,
        index,
        embedding_model=embeddings,
        k=1,
        min_score=0.70,
    )
    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["no_answer_rate"] == 1.0


def test_faq_node_uses_grounded_semantic_match_and_unknown_fallback(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clinic_faq.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))

    def fake_retrieve(query, **kwargs):
        if query == "When are you open?":
            return FAQMatch(
                answer="Verified hours.",
                question="Clinic opening hours",
                score=0.91,
                source_id="clinic-hours",
            )
        return None

    monkeypatch.setattr(agent_module, "retrieve_semantic_faq", fake_retrieve)
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "handoffs.sqlite3"))
    service = DoctorAppointmentAgent(llm_model=object())
    answer = service.faq_node({"query": "When are you open?", "messages": []}).update["messages"][0].content
    assert answer == "Verified hours.\n\nSource: clinic-hours"

    unknown_result = service.faq_node({"query": "Insurance coverage?", "messages": []})
    unknown = unknown_result.update["messages"][0].content
    assert "I’ve escalated this request" in unknown
    assert "pending human review" in unknown
    assert unknown_result.update["escalation_status"] == "pending"


def test_faq_node_refuses_medical_advice_requests(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clinic_faq.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(agent_module, "__file__", str(tmp_path / "agent.py"))
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "handoffs.sqlite3"))
    service = DoctorAppointmentAgent(llm_model=object())

    result = service.faq_node({"query": "What medicine should I take for tooth pain?", "messages": []})
    assert "can’t diagnose" in result.update["messages"][0].content
    assert "treatment" in result.update["messages"][0].content
