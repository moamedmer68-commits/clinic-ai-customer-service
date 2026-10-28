import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.types import Command

class State(TypedDict):
    messages: Annotated[list, add_messages]
    id_number: int

def supervisor_node(state: State):
    return Command(goto="my_node", update={'messages': [HumanMessage(content=f"user's identification number is {state['id_number']}")]})

def my_node(state: State):
    return {"messages": [AIMessage(content="Response to: " + state["messages"][-1].content)]}

def main():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = StateGraph(State)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("my_node", my_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("my_node", END)
    
    app = graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "1"}}
    
    print("Run 1")
    res1 = app.invoke({"messages": [HumanMessage(content="Hello")], "id_number": 123}, config)
    print("Result messages:", [m.content for m in res1["messages"]])
    
    print("Run 2")
    res2 = app.invoke({"messages": [HumanMessage(content="World")], "id_number": 123}, config)
    print("Result messages:", [m.content for m in res2["messages"]])

if __name__ == "__main__":
    main()
