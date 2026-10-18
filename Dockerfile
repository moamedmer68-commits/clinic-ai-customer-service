FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-runtime.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-runtime.txt

COPY agent.py main.py streamlit_ui.py ui_helpers.py knowledge_base.py ./
COPY data_models ./data_models
COPY prompt_library ./prompt_library
COPY toolkit ./toolkit
COPY utils ./utils
COPY support ./support
COPY data/clinic_faq.json ./data/clinic_faq.json

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/runtime-data \
    && chown -R app:app /app

USER app

EXPOSE 8003 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
