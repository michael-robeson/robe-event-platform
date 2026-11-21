FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests

RUN pip install --no-cache-dir ".[test]"

EXPOSE 9000

CMD ["uvicorn", "tests.vertical_slice.ack_fault_proxy:app", "--host", "0.0.0.0", "--port", "9000"]
