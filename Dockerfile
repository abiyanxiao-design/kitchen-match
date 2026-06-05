FROM python:3.11-slim

WORKDIR /app

COPY index.html styles.css app.js server.py README.md ./

RUN mkdir -p /app/data

ENV KITCHEN_HOST=0.0.0.0
ENV KITCHEN_PORT=8000
ENV KITCHEN_DATA_DIR=/app/data

EXPOSE 8000

CMD ["python3", "server.py"]
