FROM python:3.12-slim

WORKDIR /app

COPY ferreteria_ai/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ferreteria_ai/ .

EXPOSE 5000

CMD ["python", "main.py"]
