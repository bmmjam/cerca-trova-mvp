FROM python:3.11-slim

WORKDIR /app

# Bring source first so setuptools' src-layout (`packages.find where=["src"]`)
# resolves at install time — that's the failure that bit Nixpacks here.
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e .

# Mount point for the Railway Volume; uvicorn writes data/chunks.db here.
RUN mkdir -p /app/data

# Railway sets $PORT at runtime. Fallback 8000 lets the image run locally too.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn yti.server:app --host 0.0.0.0 --port ${PORT}"]
