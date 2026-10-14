FROM python:3.14-slim

WORKDIR /app

RUN groupadd --gid 1000 mcp && \
    useradd --uid 1000 --gid 1000 --create-home mcp

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

USER mcp
ENV PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000
ENTRYPOINT ["python", "-m", "hello_world"]
