FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY order.proto .
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. order.proto

COPY server.py .

EXPOSE 50051

CMD ["python", "server.py"]