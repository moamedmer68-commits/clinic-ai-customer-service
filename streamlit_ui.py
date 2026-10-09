import os
import uuid

import requests
import streamlit as st

from ui_helpers import escalation_details, latest_assistant_message, normalize_patient_id


API_URL = os.getenv("API_URL", "http://127.0.0.1:8003/execute")
try:
    API_TIMEOUT_SECONDS = max(5.0, min(float(os.getenv("API_TIMEOUT_SECONDS", "45")), 120.0))
except ValueError:
    API_TIMEOUT_SECONDS = 45.0
API_ACCESS_TOKEN = os.getenv("API_ACCESS_TOKEN", "").strip()


st.set_page_config(page_title="Clinic AI Assistant", page_icon="🩺", layout="centered")
st.title("Clinic AI Assistant")
st.caption("Prototype for clinic information and appointment support. Do not use for emergencies.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "transcript" not in st.session_state:
    st.session_state.transcript = []

with st.sidebar:
    st.subheader("Conversation")
    st.caption(f"Session: {st.session_state.session_id[:8]}…")
    if st.button("Start new conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.transcript = []
        st.rerun()

    patient_id_text = st.text_input(
        "Patient ID",
        key="patient_id",
        type="password",
        help="Input is masked on screen. Only use an authorized test ID while testing.",
    )
    st.caption("Conversation history is scoped to this patient and session.")
    st.divider()
    st.caption("Human escalation currently creates a local support-queue case. It does not send an email or notify a live operator.")
    if not API_ACCESS_TOKEN:
        st.warning("API access token is not configured in this UI process.") if os.getenv("REQUIRE_API_TOKEN", "").lower() == "true" else None

for entry in st.session_state.transcript:
    role = entry.get("role", "assistant")
    content = entry.get("content", "")
    if role in {"user", "assistant"} and isinstance(content, str):
        with st.chat_message(role):
            st.markdown(content, unsafe_allow_html=False)

query = st.chat_input("How can I help with your clinic appointment?")
if query:
    patient_id = normalize_patient_id(patient_id_text)
    if patient_id is None:
        st.error("Enter a numeric patient ID between 1000000 and 99999999 in the sidebar.")
    else:
        st.session_state.transcript.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query, unsafe_allow_html=False)

        headers = {"Accept": "application/json"}
        if API_ACCESS_TOKEN:
            headers["X-API-Key"] = API_ACCESS_TOKEN
        response_payload = None
        error_message = None
        with st.chat_message("assistant"):
            with st.spinner("Contacting the clinic assistant…"):
                try:
                    response = requests.post(
                        API_URL,
                        json={
                            "messages": query,
                            "id_number": patient_id,
                            "session_id": st.session_state.session_id,
                        },
                        headers=headers,
                        timeout=API_TIMEOUT_SECONDS,
                    )
                    try:
                        response_payload = response.json()
                    except ValueError:
                        response_payload = None

                    if response.status_code >= 400:
                        error_obj = response_payload.get("error", {}) if isinstance(response_payload, dict) else {}
                        error_message = error_obj.get("message") if isinstance(error_obj, dict) else None
                        if response.status_code in {401, 403}:
                            error_message = "The clinic API rejected access. Check its API token configuration."
                        elif response.status_code == 503:
                            error_message = "The clinic service is not ready. Please try again later."
                        error_message = error_message or f"The service returned status {response.status_code}."
                    elif not isinstance(response_payload, dict):
                        error_message = "The service returned an invalid response. Please try again."
                    else:
                        answer = latest_assistant_message(response_payload.get("messages"))
                        escalation = escalation_details(response_payload)
                        if escalation:
                            status = escalation["status"]
                            case_id = escalation.get("case_id")
                            if status == "pending":
                                if case_id:
                                    st.info(f"Support case {case_id} is pending human review. No human response has been received yet.")
                                else:
                                    st.info("A support case is pending human review. No human response has been received yet.")
                            elif status == "failed":
                                st.error("A support case could not be created. No human has been contacted through this system.")
                        st.markdown(answer, unsafe_allow_html=False)
                except requests.Timeout:
                    error_message = "The request timed out. Check the service and try again."
                except requests.RequestException:
                    error_message = "The clinic service is unavailable. Check the API and try again."
            if error_message:
                st.error(error_message)
                answer = error_message

        st.session_state.transcript.append({"role": "assistant", "content": answer})
