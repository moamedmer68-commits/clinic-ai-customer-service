from fastapi.testclient import TestClient
from main import app
import uuid

client = TestClient(app)

def test():
    session = str(uuid.uuid4())
    print("Session:", session)
    res = client.post("/execute", json={"id_number": 1234567, "messages": "Hello, is there a dentist available?", "session_id": session})
    print(res.json())
    res = client.post("/execute", json={"id_number": 1234567, "messages": "What about tomorrow?", "session_id": session})
    print(res.json())

test()
