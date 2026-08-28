# =========================
# Stage 1: Builder
# =========================
FROM python:3.12.14-alpine AS builder

WORKDIR /build

# Create a virtual environment
RUN python -m venv /opt/venv

# Install dependencies into the virtual environment
COPY requirements.txt .

RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# =========================
# Stage 2: Runtime
# =========================
FROM python:3.12.14-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -S appgroup && \
    adduser -S appuser -G appgroup

# Copy only the virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application files
COPY --chown=appuser:appgroup . /app/

# Use virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Switch to non-root user
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]