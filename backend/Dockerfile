FROM dhi.io/python:3-alpine-dev AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app
RUN python -m venv /app/venv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip uninstall -y pip setuptools

FROM dhi.io/python:3-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

COPY --from=builder /app/venv /app/venv
WORKDIR /app

COPY ./app /app
EXPOSE 8000

# ENTRYPOINT [ "python" ]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]