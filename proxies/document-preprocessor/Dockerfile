FROM python:3.12-slim

# If you wire in LibreOffice for .docx/.pptx/.xlsx conversion, uncomment:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#       libreoffice-core libreoffice-writer libreoffice-impress libreoffice-calc \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN groupadd --gid 1000 svc && useradd --uid 1000 --gid 1000 --create-home svc

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

USER svc
ENV PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8082
EXPOSE 8082
ENTRYPOINT ["python", "-m", "proxy"]
