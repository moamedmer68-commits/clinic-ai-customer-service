import streamlit as st
import requests
import uuid

API_URL = "http://127.0.0.1:8003/execute"

st.title("Doctor Appointment Assistant")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "transcript" not in st.session_state:
    st.session_state.transcript = []

with st.sidebar:
    st.caption("Conversation memory is scoped to this patient and conversation.")
    if st.button("Start new conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.transcript = []
        st.rerun()

user_id = st.text_input("Patient ID number", key="patient_id")
for entry in st.session_state.transcript:
    with st.chat_message(entry["role"]):
        st.write(entry["content"])

query = st.chat_input("How can I help with your appointment?")
if query:
    if not user_id.isdigit():
        st.error("Enter a valid numeric patient ID first.")
    else:
        st.session_state.transcript.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.write(query)
        try:
            response = requests.post(
                API_URL,
                json={"messages": query, "id_number": int(user_id), "session_id": st.session_state.session_id},
                timeout=45,
            )
            response.raise_for_status()
            messages = response.json().get("messages", [])
            answer = next((m.get("content") for m in reversed(messages) if m.get("type") == "ai"), "I couldn't find a response.")
            if not isinstance(answer, str):
                answer = str(answer)
            st.session_state.transcript.append({"role": "assistant", "content": answer})
            with st.chat_message("assistant"):
                st.write(answer)
        except requests.RequestException:
            st.error("The appointment service is unavailable. Please try again.")
