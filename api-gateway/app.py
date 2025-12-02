from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import grpc
import pika
import json
import os
from zeep import Client
from zeep.transports import Transport
from requests import Session
import logging
import sys

# logging info
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# grpc import
try:
    import order_pb2
    import order_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    logger.warning(f"gRPC modules not available: {e}")
    GRPC_AVAILABLE = False

app = FastAPI(title="Order System API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# config
SOAP_SERVICE_URL = os.getenv("SOAP_SERVICE_URL", "http://product-validator:8080/ws/ProductValidator?wsdl")
GRPC_SERVICE_HOST = os.getenv("GRPC_SERVICE_HOST", "order-processor")
GRPC_SERVICE_PORT = os.getenv("GRPC_SERVICE_PORT", "50051")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")

# models
class OrderRequest(BaseModel):
    product_id: str
    email: EmailStr
    quantity: int = 1

class OrderResponse(BaseModel):
    order_id: str
    status: str
    product_id: str
    email: str
    quantity: int
    links: dict = Field(..., alias="_links")
    
    class Config:
        populate_by_name = True

# hateoas links generator
def get_hateoas_links(order_id: str) -> dict:
    return {
        "self": {"href": f"{API_GATEWAY_URL}/orders/{order_id}"},
        "status": {"href": f"{API_GATEWAY_URL}/orders/{order_id}/status"},
        "cancel": {"href": f"{API_GATEWAY_URL}/orders/{order_id}/cancel"},
        "all-orders": {"href": f"{API_GATEWAY_URL}/orders"}
    }

# soap validation method
def validate_product_soap(product_id: str) -> bool:
    try:
        logger.info(f"Validation of {product_id} through SOAP...")
        session = Session()
        session.timeout = 10
        transport = Transport(session=session)
        soap_client = Client(SOAP_SERVICE_URL, transport=transport)
        result = soap_client.service.validateProduct(product_id)
        logger.info(f"SOAP validation result: {result}")
        return result
    except Exception as e:
        logger.error(f"SOAP validation error: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Valdation service unavailable: {str(e)}")

# order processing using grpc
def process_order_grpc(product_id: str, email: str, quantity: int) -> str:
    if not GRPC_AVAILABLE:
        raise HTTPException(status_code=503, detail="gRPC is not available")
    
    try:
        logger.info(f"Order processing via gRPC...")
        channel = grpc.insecure_channel(f"{GRPC_SERVICE_HOST}:{GRPC_SERVICE_PORT}")
        stub = order_pb2_grpc.OrderProcessorStub(channel)
        
        request = order_pb2.OrderRequest(
            product_id=product_id,
            email=email,
            quantity=quantity
        )
        
        response = stub.ProcessOrder(request)
        logger.info(f"Order has been processed, ID: {response.order_id}")
        channel.close()
        return response.order_id
    except Exception as e:
        logger.error(f"gRPC processing error: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Processing service unavailable: {str(e)}")

# rabbitmq notif sender
def send_notification_rabbitmq(order_id: str, email: str):
    try:
        logger.info(f"Sending notification to RabbitMQ...")
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='notifications', durable=True)
        
        message = {
            "order_id": order_id,
            "email": email,
            "type": "order_confirmation"
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='notifications',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        
        logger.info(f"Notification sent")
        connection.close()
    except Exception as e:
        logger.error(f"Error sending to RabbitMQ: {str(e)}")

# main endpoint
@app.get("/")
async def root():
    return {
        "message": "Order System API Gateway",
        "_links": {
            "self": {"href": f"{API_GATEWAY_URL}/"},
            "orders": {"href": f"{API_GATEWAY_URL}/orders"},
            "health": {"href": f"{API_GATEWAY_URL}/health"}
        }
    }

# health check
@app.get("/health")
async def health():
    return {"status": "healthy"}

# creating order method + endpoint
@app.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(order: OrderRequest):
    logger.info(f"Received order placement request: {order}")
    
    # soap validation
    is_valid = validate_product_soap(order.product_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Produt {order.product_id} is unavilable")
    
    # grpc processing
    order_id = process_order_grpc(order.product_id, order.email, order.quantity)
    
    # rabbitmq sender
    send_notification_rabbitmq(order_id, order.email)
    
    # hateoas response
    response = OrderResponse(
        order_id=order_id,
        status="accepted",
        product_id=order.product_id,
        email=order.email,
        quantity=order.quantity,
        _links=get_hateoas_links(order_id)
    )
    
    logger.info(f"Order {order_id} placed")
    return response

# get order main
@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    return {
        "order_id": order_id,
        "status": "processing",
        "_links": get_hateoas_links(order_id)
    }

# order status
@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: str):
    return {
        "order_id": order_id,
        "status": "processing",
        "last_updated": "2024-01-01T12:00:00Z",
        "_links": get_hateoas_links(order_id)
    }

# order cancel
@app.delete("/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    return {
        "order_id": order_id,
        "status": "cancelled",
        "_links": get_hateoas_links(order_id)
    }

# list of orders
@app.get("/orders")
async def list_orders():
    return {
        "orders": [],
        "_links": {
            "self": {"href": f"{API_GATEWAY_URL}/orders"}
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)