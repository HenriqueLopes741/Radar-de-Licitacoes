FROM python:3.12-slim

WORKDIR /app

# Dependências antes do código: mudar só o app não reinstala tudo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# O app importa "from dashboard import consultas", então o pacote
# precisa estar numa pasta dashboard/ dentro de um diretório do PYTHONPATH
COPY . dashboard/
ENV PYTHONPATH=/app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# headless: sem a pergunta de e-mail do primeiro uso, que travaria o container
CMD ["streamlit", "run", "dashboard/app.py", "--server.headless=true", "--server.address=0.0.0.0"]
