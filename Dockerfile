# Production image:  docker build -t voiceai .  &&  docker run -p 8000:8000 --env-file .env -v voiceai-data:/data voiceai
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/restaurant.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data && useradd --create-home appuser && chown -R appuser /data /app
USER appuser

EXPOSE 8000
# First start: creates the database with the starter menu if it does not exist yet.
CMD ["sh", "-c", "[ -f \"$DATABASE_PATH\" ] || python -m app.seed_menu; exec gunicorn -w 2 --threads 4 -b 0.0.0.0:8000 --access-logfile - run:app"]
