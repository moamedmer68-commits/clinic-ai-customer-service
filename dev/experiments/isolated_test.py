import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

class State(TypedDict):
    messages: Annotated[list, add_messages]

def my_node(state: State):
    return {"messages": [HumanMessage(content="Response!")]}

def main():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = StateGraph(State)
    graph.add_node("my_node", my_node)
    graph.add_edge(START, "my_node")
    graph.add_edge("my_node", END)
    
    app = graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "1"}}
    app.invoke({"messages": [HumanMessage(content="Hello")]}, config)
    
    state = app.get_state(config)
    print("State:", state.values)

if __name__ == "__main__":
    main()
