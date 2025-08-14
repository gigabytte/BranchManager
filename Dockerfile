# Build stage - Install UV and dependencies
FROM python:3.13-alpine3.22 AS builder

# Install system dependencies needed for building Python packages
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    git \
    curl

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Copy source code and other required files
COPY src/ src/
COPY README.md ./

# Create virtual environment explicitly and install dependencies
RUN uv venv /app/.venv
RUN uv sync --frozen

# Build the package
RUN uv build

# Runtime stage - Minimal Alpine image
FROM python:3.13-alpine3.22 AS runtime

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Install runtime dependencies only
RUN apk add --no-cache \
    ca-certificates \
    tzdata

# Copy UV from builder stage
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy built package and install it using UV's pip interface
COPY --from=builder /app/dist/*.whl /tmp/
RUN uv pip install --python /app/.venv/bin/python /tmp/*.whl && rm /tmp/*.whl

# Create directory for config files
RUN mkdir -p /app/config && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV="/app/.venv"

# Default command
ENTRYPOINT ["branch-manager"]
