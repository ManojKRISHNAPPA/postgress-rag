# Debian wheels are a better default for FAISS than Alpine/musl.
# Pin this image to an approved digest in your deployment pipeline.
FROM python:3.12-slim
WORKDIR /app
COPY production/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && useradd --create-home --uid 10001 rag \
    && mkdir -p /app/.cache/production \
    && chown -R rag:rag /app/.cache
COPY --chown=rag:rag production /app/production
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER rag
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)"
CMD ["streamlit", "run", "production/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]