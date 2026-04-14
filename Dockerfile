FROM python:3.11-slim

WORKDIR /app

COPY simple_http_server.py .
COPY simple.html .

EXPOSE 8080

CMD ["python", "simple_http_server.py"]
