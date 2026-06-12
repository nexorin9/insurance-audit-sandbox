FROM python:3.11-slim

WORKDIR /app

# Install Node.js 18
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend package files and install dependencies
COPY src/frontend/package.json src/frontend/package-lock.json* src/frontend/
RUN cd src/frontend && npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Build frontend
RUN cd src/frontend && npm run build

# Expose port
EXPOSE 8000

# Start FastAPI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]