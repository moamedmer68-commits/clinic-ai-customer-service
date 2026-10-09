import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

import main
from utils.session import make_thread_id


class MemoryState(TypedDict):
    messages: Annotated[list, add_messages]


def respond(state: MemoryState):
    latest = next(message.content for message in reversed(state["messages"]) if isinstance(message, HumanMessage))
    return {"messages": [AIMessage(content=f"received: {latest}")]}


def build_memory_graph(db_path):
    connection = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    builder = StateGraph(MemoryState)
    builder.add_node("respond", respond)
    builder.add_edge(START, "respond")
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=saver), connection


def test_api_preserves_turns_and_isolates_patient_and_session(monkeypatch, tmp_path, authorized_test_client):
    db_path = tmp_path / "memory.sqlite3"
    monkeypatch.setattr(main, "_build_graph", lambda: build_memory_graph(db_path))
    with authorized_test_client(main.create_app()) as client:
        first = client.post("/execute", json={"id_number": 1234567, "messages": "I need a dentist", "session_id": "visit-a"})
        second = client.post("/execute", json={"id_number": 1234567, "messages": "At 10 tomorrow", "session_id": "visit-a"})
        separate_session = client.post("/execute", json={"id_number": 1234567, "messages": "New topic", "session_id": "visit-b"})
        separate_patient = client.post("/execute", json={"id_number": 7654321, "messages": "Private topic", "session_id": "visit-a"})
    assert first.status_code == second.status_code == separate_session.status_code == separate_patient.status_code == 200
    assert [m["content"] for m in second.json()["messages"] if m["type"] == "human"] == ["I need a dentist", "At 10 tomorrow"]
    assert [m["content"] for m in separate_session.json()["messages"] if m["type"] == "human"] == ["New topic"]
    assert [m["content"] for m in separate_patient.json()["messages"] if m["type"] == "human"] == ["Private topic"]


def test_api_memory_survives_application_restart(monkeypatch, tmp_path, authorized_test_client):
    db_path = tmp_path / "restart.sqlite3"
    monkeypatch.setattr(main, "_build_graph", lambda: build_memory_graph(db_path))
    payload = {"id_number": 1234567, "session_id": "persistent-session"}
    with authorized_test_client(main.create_app()) as first_client:
        first = first_client.post("/execute", json={**payload, "messages": "remember this"})
    with authorized_test_client(main.create_app()) as second_client:
        second = second_client.post("/execute", json={**payload, "messages": "continue"})
    assert first.status_code == second.status_code == 200
    human_turns = [m["content"] for m in second.json()["messages"] if m["type"] == "human"]
    assert human_turns == ["remember this", "continue"]


def test_thread_id_is_stable_patient_scoped_and_does_not_expose_id():
    first = make_thread_id(1234567, "session-a")
    assert first == make_thread_id(1234567, "session-a")
    assert first != make_thread_id(7654321, "session-a")
    assert first != make_thread_id(1234567, "session-b")
    assert "1234567" not in first
