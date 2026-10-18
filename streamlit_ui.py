from __future__ import annotations

import os
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from ui_helpers import escalation_details, latest_assistant_message, normalize_patient_id

API_URL = os.getenv("API_URL", "http://127.0.0.1:8003/execute")
try:
    API_TIMEOUT_SECONDS = max(5.0, min(float(os.getenv("API_TIMEOUT_SECONDS", "45")), 120.0))
except ValueError:
    API_TIMEOUT_SECONDS = 45.0
API_ACCESS_TOKEN = os.getenv("API_ACCESS_TOKEN", "").strip()

st.set_page_config(page_title="CareDesk | Clinic Assistant", page_icon="✚", layout="wide", initial_sidebar_state="expanded")

# Keep all user-provided content rendered through Streamlit's safe Markdown path.
st.markdown(
    """
    <style>
    :root { --care-ink:#142b3b; --care-muted:#63798a; --care-teal:#087f8c; --care-teal-dark:#066875; --care-bg:#f4f8fa; --care-line:#dce7ec; }
    .stApp { background: radial-gradient(circle at 8% 0%, rgba(8,127,140,.08), transparent 26rem), var(--care-bg); color:var(--care-ink); }
    [data-testid="stHeader"] { background:rgba(244,248,250,.82); }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#102d40 0%,#173e51 100%); }
    [data-testid="stSidebar"] * { color:#f3f8fb !important; }
    [data-testid="stSidebar"] input { color:#142b3b !important; background:#fff !important; }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] { background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.22); }
    .block-container { max-width:1120px; padding-top:2rem; padding-bottom:3rem; }
    .care-hero { border-radius:24px; padding:1.7rem 1.8rem; background:linear-gradient(115deg,#10384b 0%,#087f8c 72%,#24a6a0 100%); color:#fff; box-shadow:0 18px 42px rgba(16,56,75,.15); margin-bottom:1.2rem; }
    .care-eyebrow { font-size:.78rem; text-transform:uppercase; letter-spacing:.14em; opacity:.82; font-weight:750; }
    .care-title { font-size:clamp(1.7rem,3.2vw,2.5rem); line-height:1.15; font-weight:800; letter-spacing:-.035em; margin:.55rem 0 .5rem; }
    .care-subtitle { font-size:1rem; max-width:680px; line-height:1.65; opacity:.9; }
    .care-pill { display:inline-block; border:1px solid rgba(255,255,255,.34); border-radius:999px; padding:.35rem .7rem; margin-top:1rem; font-size:.8rem; }
    .care-info { background:#fff; border:1px solid var(--care-line); border-radius:16px; padding:1rem 1.1rem; min-height:96px; box-shadow:0 5px 18px rgba(18,55,74,.035); }
    .care-info-label { color:var(--care-muted); font-size:.78rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; }
    .care-info-value { color:var(--care-ink); font-size:1.05rem; font-weight:750; margin-top:.35rem; }
    [data-testid="stChatMessage"] { border:1px solid var(--care-line); background:#fff; border-radius:18px; padding:1rem 1.15rem; margin:.75rem 0; box-shadow:0 5px 18px rgba(18,55,74,.035); }
    [data-testid="stChatInput"] { border-radius:16px; }
    [data-testid="stChatInput"] textarea { min-height:58px; }
    [data-testid="stBaseButton-primary"] { background:var(--care-teal); border-color:var(--care-teal); }
    [data-testid="stBaseButton-primary"]:hover { background:var(--care-teal-dark); border-color:var(--care-teal-dark); }
    div[data-testid="stAlert"] { border-radius:14px; }
    .care-footnote { color:var(--care-muted); font-size:.82rem; padding-top:.7rem; }
    @media (max-width: 700px) { .block-container { padding:1rem .8rem 2rem; } .care-hero { padding:1.25rem; border-radius:18px; } .care-title { font-size:1.75rem; } [data-testid="stChatMessage"] { padding:.75rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "transcript" not in st.session_state:
    st.session_state.transcript = []
if "language" not in st.session_state:
    st.session_state.language = "English"

AR = st.session_state.language == "العربية"
TXT = {
    "brand": "مساعد العيادة الذكي" if AR else "CareDesk Clinic Assistant",
    "eyebrow": "رعاية أوضح. حجز أسهل." if AR else "CLINIC SUPPORT, MADE SIMPLE",
    "title": "إزاي نقدر نساعدك النهارده؟" if AR else "How can we help today?",
    "subtitle": "اسأل عن خدمات العيادة أو المواعيد، أو اطلب مساعدة في الحجز. المساعد لا يقدم تشخيصًا طبيًا." if AR else "Ask about clinic information and appointments, or get help with booking. This assistant does not provide medical diagnoses.",
    "prototype": "نسخة تجريبية" if AR else "Prototype experience",
    "new": "بدء محادثة جديدة" if AR else "Start new conversation",
    "session": "الجلسة" if AR else "SESSION",
    "patient": "رقم المريض التجريبي" if AR else "Demo Patient ID",
    "patient_help": "استخدم رقم اختبار فقط. هذا الحقل لا ينشئ حساب مريض ولا يثبت الهوية." if AR else "Use a test ID only. This field does not create a patient account or verify identity.",
    "privacy": "يتم فصل سياق المحادثة حسب رقم المريض والجلسة." if AR else "Conversation context is scoped to the patient ID and session.",
    "handoff": "التصعيد ينشئ حالة في طابور محلي فقط ولا يُخطر موظفًا حقيقيًا." if AR else "Escalation creates a local queue case only; it does not notify a live operator.",
    "token_warning": "رمز API غير مضبوط. الخدمة سترفض الطلبات حتى يتم ضبطه." if AR else "API_ACCESS_TOKEN is not configured. Requests will be rejected until it is set.",
    "placeholder": "اكتب رسالتك هنا…" if AR else "Type your message here…",
    "welcome": "ابدأ بسؤال عن المعلومات أو المواعيد. لا تدخل بيانات طبية حساسة." if AR else "Start with a question about clinic information or appointments. Do not enter sensitive medical details.",
    "invalid_id": "أدخل رقم مريض رقميًا من 1000000 إلى 99999999." if AR else "Enter a numeric patient ID between 1000000 and 99999999.",
    "contacting": "جاري الاتصال بالمساعد…" if AR else "Contacting the clinic assistant…",
    "api_rejected": "رفضت خدمة العيادة الوصول. راجع إعداد رمز API." if AR else "The clinic API rejected access. Check its API token configuration.",
    "not_ready": "الخدمة غير جاهزة حاليًا. حاول لاحقًا." if AR else "The clinic service is not ready. Please try again later.",
    "invalid_response": "أعادت الخدمة استجابة غير صالحة. حاول مرة أخرى." if AR else "The service returned an invalid response. Please try again.",
    "timeout": "انتهت مهلة الطلب. تحقق من الخدمة ثم حاول مرة أخرى." if AR else "The request timed out. Check the service and try again.",
    "unavailable": "الخدمة غير متاحة حاليًا. تحقق من تشغيل API." if AR else "The clinic service is unavailable. Check the API and try again.",
    "case_pending": "حالة الدعم {case_id} تنتظر مراجعة بشرية. لم يصل رد من موظف حتى الآن." if AR else "Support case {case_id} is pending human review. No human response has been received yet.",
    "case_pending_no_id": "حالة الدعم تنتظر مراجعة بشرية. لم يصل رد من موظف حتى الآن." if AR else "A support case is pending human review. No human response has been received yet.",
    "case_failed": "تعذر إنشاء حالة الدعم. لم يتم التواصل مع موظف عبر النظام." if AR else "A support case could not be created. No human has been contacted through this system.",
    "footer": "عرض تجريبي ببيانات غير حقيقية — لا تستخدمه لحجز موعد فعلي أو للطوارئ." if AR else "Demo with synthetic data — not for real bookings or emergencies.",
}

with st.sidebar:
    st.markdown(f"### ✚ {TXT['brand']}")
    st.caption("LANGUAGE / اللغة")
    selected_language = st.selectbox("Language / اللغة", ["English", "العربية"], index=0 if st.session_state.language == "English" else 1, label_visibility="collapsed")
    if selected_language != st.session_state.language:
        st.session_state.language = selected_language
        st.rerun()
    st.divider()
    st.subheader("المحادثة" if AR else "Your conversation")
    st.caption(f"{TXT['session']}: {st.session_state.session_id[:8]}…")
    if st.button(TXT["new"], use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.transcript = []
        st.rerun()
    patient_id_text = st.text_input(
        TXT["patient"], key="patient_id", type="password", max_chars=8,
        help=TXT["patient_help"],
    )
    st.caption(TXT["privacy"])
    st.divider()
    st.caption(TXT["handoff"])
    if not API_ACCESS_TOKEN and os.getenv("ALLOW_UNAUTHENTICATED_LOCAL_DEV", "").strip().lower() != "true":
        st.warning(TXT["token_warning"])

st.markdown(
    f"""<section class="care-hero" dir="{'rtl' if AR else 'ltr'}">
    <div class="care-eyebrow">{TXT['eyebrow']}</div>
    <div class="care-title">{TXT['title']}</div>
    <div class="care-subtitle">{TXT['subtitle']}</div>
    <span class="care-pill">✦ {TXT['prototype']}</span>
    </section>""",
    unsafe_allow_html=True,
)

metric1, metric2, metric3 = st.columns(3)
with metric1:
    st.markdown(f'<div class="care-info"><div class="care-info-label">{"الحالة" if AR else "SERVICE"}</div><div class="care-info-value">{"مساعد معلومات ومواعيد" if AR else "Information & appointments"}</div></div>', unsafe_allow_html=True)
with metric2:
    st.markdown(f'<div class="care-info"><div class="care-info-label">{"اللغة" if AR else "LANGUAGE"}</div><div class="care-info-value">{"العربية والإنجليزية" if AR else "Arabic & English UI"}</div></div>', unsafe_allow_html=True)
with metric3:
    st.markdown(f'<div class="care-info"><div class="care-info-label">{"الخصوصية" if AR else "PRIVACY"}</div><div class="care-info-value">{"سياق منفصل للجلسة" if AR else "Session-scoped context"}</div></div>', unsafe_allow_html=True)

if not st.session_state.transcript:
    st.info(TXT["welcome"])

for entry in st.session_state.transcript:
    role = entry.get("role", "assistant")
    content = entry.get("content", "")
    if role in {"user", "assistant"} and isinstance(content, str):
        with st.chat_message(role):
            st.markdown(content, unsafe_allow_html=False)

query = st.chat_input(TXT["placeholder"])
if query:
    patient_id = normalize_patient_id(patient_id_text)
    if patient_id is None:
        st.error(TXT["invalid_id"])
    else:
        st.session_state.transcript.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query, unsafe_allow_html=False)

        headers = {"Accept": "application/json"}
        if API_ACCESS_TOKEN:
            headers["X-API-Key"] = API_ACCESS_TOKEN
        response_payload = None
        error_message = None
        answer = ""
        with st.chat_message("assistant"):
            with st.spinner(TXT["contacting"]):
                try:
                    response = requests.post(
                        API_URL,
                        json={"messages": query, "id_number": patient_id, "session_id": st.session_state.session_id},
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
                            error_message = TXT["api_rejected"]
                        elif response.status_code == 503:
                            error_message = TXT["not_ready"]
                        error_message = error_message or (f"HTTP {response.status_code}" if not AR else f"خطأ HTTP {response.status_code}")
                    elif not isinstance(response_payload, dict):
                        error_message = TXT["invalid_response"]
                    else:
                        answer = latest_assistant_message(response_payload.get("messages"))
                        escalation = escalation_details(response_payload)
                        if escalation:
                            status = escalation["status"]
                            case_id = escalation.get("case_id")
                            if status == "pending":
                                st.info(TXT["case_pending"].format(case_id=case_id) if case_id else TXT["case_pending_no_id"])
                            elif status == "failed":
                                st.error(TXT["case_failed"])
                        st.markdown(answer, unsafe_allow_html=False)
                except requests.Timeout:
                    error_message = TXT["timeout"]
                except requests.RequestException:
                    error_message = TXT["unavailable"]
            if error_message:
                st.error(error_message)
                answer = error_message
        st.session_state.transcript.append({"role": "assistant", "content": answer})

st.markdown(f'<div class="care-footnote" dir="{"rtl" if AR else "ltr"}">ⓘ {TXT["footer"]}</div>', unsafe_allow_html=True)
