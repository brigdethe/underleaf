# Multi-stage / lightweight Debian Python with TeX Live for Underleaf
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install pdflatex and required LaTeX packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and source code
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python package and production dependencies
RUN pip install --no-cache-dir .

# Default configuration
ENV MYOVERL_DATA=/app/data \
    HOST=0.0.0.0 \
    PORT=8765

RUN mkdir -p /app/data

EXPOSE 8765

CMD ["python", "-m", "myoverl_mcp.app"]
