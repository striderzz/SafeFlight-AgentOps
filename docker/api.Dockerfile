FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/striderzz/SafeFlight-AgentOps" \
      org.opencontainers.image.description="SafeFlight API: CrewAI flow and FastAPI"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    CREWAI_DISABLE_TELEMETRY=true
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY safeflight ./safeflight
RUN useradd --create-home --uid 1000 app && mkdir -p var && chown app var
USER app
EXPOSE 8000
CMD ["uvicorn", "safeflight.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
