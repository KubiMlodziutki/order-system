FROM python:3.11-slim

WORKDIR /app

# copy files
COPY requirements.txt .
COPY app.py .
COPY order_pb2.py .
COPY order_pb2_grpc.py .
COPY tests/ /app/tests/

# Irequirements.txt downloar
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]