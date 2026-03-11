# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IARA Core — Dockerfile (Python 3.12)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FROM python:3.12-slim

# Instala dependências de sistema (git para SOP versioning, docker CLI para sandbox)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        docker.io && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código fonte
COPY . .

# Inicializa o repositório Git para versionamento de SOPs
RUN git config --global user.email "iara@zeroclaw.local" && \
    git config --global user.name "IARA SOP Tracker" && \
    cd /app/roles && git init && git add . && git commit -m "IARA: SOPs iniciais" --allow-empty || true && \
    cd /app/skills && git init && git add . && git commit -m "IARA: Skills iniciais" --allow-empty || true

EXPOSE 8000

# Entrypoint: bootstrap das rotas semânticas + execução principal
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
