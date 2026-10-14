# Pin by digest in production (python:3.14-slim@sha256:...), Renovate-bumped.
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build-time self-check: content YAML loads, main.py imports, CO2 formatting
# and the dashboard host gate behave. httpx is only needed for the test client.
RUN python -c "import yaml; yaml.safe_load(open('content/carbon_info.yaml'))" \
 && pip install --no-cache-dir httpx==0.28.1 \
 && python test_app.py \
 && pip uninstall -y httpx \
 && echo "cost-tracker build smoke OK"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=40s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
