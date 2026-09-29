import sqlite3
import unittest

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from utils.session import make_thread_id

class ConversationState(TypedDict):
    messages: Annotated[list, add_messages]

def append_message(state: ConversationState):
    return {"messages": [HumanMessage(content="checkpointed")]}

class TestConversationMemory(unittest.TestCase):
    def test_thread_id_is_stable_and_patient_scoped(self):
        self.assertEqual(make_thread_id(1234567, "session-a"), make_thread_id(1234567, "session-a"))
        self.assertNotEqual(make_thread_id(1234567, "session-a"), make_thread_id(7654321, "session-a"))
        self.assertNotEqual(make_thread_id(1234567, "session-a"), make_thread_id(1234567, "session-b"))
        self.assertNotIn("1234567", make_thread_id(1234567, "session-a"))

    def test_sqlite_checkpointer_persists_state_between_invocations(self):
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        checkpointer = SqliteSaver(connection)
        graph_builder = StateGraph(ConversationState)
        graph_builder.add_node("append", append_message)
        graph_builder.add_edge(START, "append")
        graph_builder.add_edge("append", END)
        graph = graph_builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "patient-session-1"}}

        graph.invoke({"messages": [HumanMessage(content="hello")]}, config=config)
        saved = graph.get_state(config).values["messages"]
        self.assertEqual([message.content for message in saved], ["hello", "checkpointed"])

        other_config = {"configurable": {"thread_id": "patient-session-2"}}
        graph.invoke({"messages": [HumanMessage(content="separate") ]}, config=other_config)
        other_saved = graph.get_state(other_config).values["messages"]
        self.assertEqual([message.content for message in other_saved], ["separate", "checkpointed"])
        self.assertEqual([message.content for message in graph.get_state(config).values["messages"]], ["hello", "checkpointed"])
        
        # Test multi-turn deduplication logic (add_messages handles IDs properly)
        graph.invoke({"messages": [HumanMessage(content="follow-up")]}, config=config)
        updated_saved = graph.get_state(config).values["messages"]
        self.assertEqual([message.content for message in updated_saved], ["hello", "checkpointed", "follow-up", "checkpointed"])
        
        connection.close()

if __name__ == "__main__":
    unittest.main()
