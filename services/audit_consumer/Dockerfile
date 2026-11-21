FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY services/audit_consumer/db ./services/audit_consumer/db

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "robe_event_platform.audit_consumer:app", "--host", "0.0.0.0", "--port", "8000"]
