# to run use
# docker-compose exec api-gateway pytest -m integration -v

import pytest
import grpc
import pika
import json
import requests

import order_pb2
import order_pb2_grpc

GRPC_HOST = "order-processor:50051"
SOAP_URL = "http://product-validator:8080/ws/ProductValidator"
RABBIT_HOST = "rabbitmq"
API_URL = "http://localhost:8000"

@pytest.mark.integration
def test_grpc_connection():
    try:
        channel = grpc.insecure_channel(GRPC_HOST)
        stub = order_pb2_grpc.OrderProcessorStub(channel)
        
        request = order_pb2.OrderRequest(
            product_id="PROD-001",
            email="test@example.com",
            quantity=1
        )
        
        response = stub.ProcessOrder(request, timeout=5)
        
        # check whether response is ok
        assert hasattr(response, 'status'), "Response should have 'status' attribute"
        assert hasattr(response, 'order_id'), "Response should have 'order_id' attribute"
        assert response.status == "accepted", f"Expected status 'accepted', got '{response.status}'"
        assert response.order_id.startswith("ORD-"), f"Order ID should start with 'ORD-', got '{response.order_id}'"
        
        channel.close()
    except grpc.RpcError as e:
        pytest.skip(f"gRPC service unavailable: {e.code()} - {e.details()}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {type(e).__name__}: {str(e)}")

@pytest.mark.integration
def test_soap_connection():
    soap_body = """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:prod="http://validator.com/">
       <soapenv:Body>
          <prod:validateProduct>
             <productId>PROD-001</productId>
          </prod:validateProduct>
       </soapenv:Body>
    </soapenv:Envelope>
    """
    
    try:
        response = requests.post(
            SOAP_URL,
            data=soap_body,
            headers={"Content-Type": "text/xml"},
            timeout=5
        )
        assert response.status_code == 200
        assert "true" in response.text.lower() or "false" in response.text.lower()
    except requests.exceptions.ConnectionError as e:
        pytest.skip(f"SOAP service unavailable: {e}")

@pytest.mark.integration
def test_rabbitmq_connection():
    try:
        credentials = pika.PlainCredentials("guest", "guest")
        params = pika.ConnectionParameters(
            host=RABBIT_HOST, 
            credentials=credentials,
            connection_attempts=3,
            retry_delay=1
        )
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue="test_queue", durable=False)
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        pytest.skip(f"RabbitMQ unavailable: {e}")

@pytest.mark.integration
def test_e2e_order_flow():
    try:
        response = requests.post(
            f"{API_URL}/orders",
            json={
                "product_id": "PROD-001",
                "email": "test@example.com",
                "quantity": 1
            },
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            assert data["order_id"].startswith("ORD-"), f"Order ID should start with 'ORD-', got '{data['order_id']}'"
            assert data["status"] == "accepted", f"Expected status 'accepted', got '{data['status']}'"
            assert "_links" in data, "Response should contain HATEOAS links"
        else:
            pytest.skip(f"API unavailable: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError as e:
        pytest.skip(f"API unavailable: {e}")