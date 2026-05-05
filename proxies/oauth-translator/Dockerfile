FROM python:3.12-slim

WORKDIR /app
RUN groupadd --gid 1000 svc && useradd --uid 1000 --gid 1000 --create-home svc

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

USER svc
ENV PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8080
EXPOSE 8080
ENTRYPOINT ["python", "-m", "proxy"]
