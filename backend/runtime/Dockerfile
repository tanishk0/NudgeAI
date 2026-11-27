FROM python:3.12-slim
RUN pip install --no-cache-dir Flask==3.1.2 tenacity==9.1.2 && useradd --uid 1000 --create-home learner
USER learner
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
