# Cloud Run container for the Hosted Analytics Agent.
# Build/deploy happens server-side via `gcloud run deploy --source .`
# (Cloud Build + Artifact Registry, per the sponsor's setup guide - no
# local Docker needed).

FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ app/
COPY semantics/ semantics/

# Cloud Run injects PORT; identity comes from the attached service account
# (no keys anywhere in this image).
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
