from main import app_graph
from utils.session import make_thread_id
from langchain_core.messages import HumanMessage
import uuid

def test():
    session = str(uuid.uuid4())
    print("Session:", session)
    thread_id = make_thread_id(1234567, session)
    
    config = {"recursion_limit": 20, "configurable": {"thread_id": thread_id}}
    
    query_data = {
        "messages": [HumanMessage(content="Hello, is there a dentist available?")],
        "id_number": 1234567,
        "next": "",
        "query": "",
        "current_reasoning": "",
    }
    
    print("First run...")
    # This might fail if the model requires API keys, but let's see.
    try:
        response = app_graph.invoke(query_data, config=config)
        print("Response 1:", response)
    except Exception as e:
        print("Error 1:", e)

test()
