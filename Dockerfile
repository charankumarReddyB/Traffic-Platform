FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for psycopg2 and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy entire repository (frontend, backend, run.py)
COPY . .

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=""
ENV NETWORK_FILE="backend/network.json"
ENV FRONTEND_DIR="/app/frontend"

EXPOSE 8000

# Run migrations and launch platform
CMD ["sh", "-c", "cd backend && alembic upgrade head && cd /app && python run.py --host 0.0.0.0 --port 8000"]
