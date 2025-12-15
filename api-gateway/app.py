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

#  HATEOAS gen needs base URL
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import gRPC
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

# Config
SOAP_SERVICE_URL = os.getenv("SOAP_SERVICE_URL", "http://product-validator:8080/ws/ProductValidator?wsdl")
GRPC_SERVICE_HOST = os.getenv("GRPC_SERVICE_HOST", "order-processor")
GRPC_SERVICE_PORT = os.getenv("GRPC_SERVICE_PORT", "50051")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")


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


def get_hateoas_links(order_id: str, current_status: str) -> dict:
    links = {
        "self": {"href": f"{API_GATEWAY_URL}/orders/{order_id}"},
        "all-orders": {"href": f"{API_GATEWAY_URL}/orders"}
    }
    
    # dynamic links based on status
    if current_status != "cancelled":
         links["status"] = {"href": f"{API_GATEWAY_URL}/orders/{order_id}/status"}
         links["cancel"] = {"href": f"{API_GATEWAY_URL}/orders/{order_id}/cancel"}
    
    return links

def get_grpc_stub():
    channel = grpc.insecure_channel(f"{GRPC_SERVICE_HOST}:{GRPC_SERVICE_PORT}")
    return order_pb2_grpc.OrderProcessorStub(channel), channel

def send_notification_rabbitmq(order_id: str, email: str, status: str):
    try:
        credentials = pika.PlainCredentials('guest', 'guest')
        params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='notifications', durable=True)
        
        message = {
            "order_id": order_id,
            "email": email,
            "type": "status_update",
            "new_status": status
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='notifications',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        logger.error(f"RabbitMQ Error: {e}")

# --- Endpoints ---

@app.get("/products")
async def get_products():
    """
    Frontend - Gateway - gRPC - SOAP - gRPC - Gateway - Frontend
    """
    if not GRPC_AVAILABLE:
        raise HTTPException(status_code=503, detail="gRPC unavailable")
    
    try:
        stub, channel = get_grpc_stub()

        response = stub.GetAvailableProducts(order_pb2.Empty())
        channel.close()
        
        # Protobuf -> JSON (Dict)
        products_data = []
        for p in response.products:
            products_data.append({
                "id": p.id,
                "name": p.name,
                "icon": p.icon
            })
            
        return {"products": products_data}
        
    except grpc.RpcError as e:
        logger.error(f"gRPC Error: {e}")
        raise HTTPException(status_code=503, detail="Could not fetch products")

@app.get("/orders")
async def get_all_orders():
    if not GRPC_AVAILABLE:
        return {"orders": []}
        
    try:
        stub, channel = get_grpc_stub()
        response = stub.GetAllOrders(order_pb2.Empty())
        channel.close()
        
        orders_data = []
        for o in response.orders:
            orders_data.append({
                "order_id": o.order_id,
                "status": o.status,
                "product_id": o.product_id,
                "email": o.email,
                "quantity": o.quantity,
                # HATEOAS 
                "_links": get_hateoas_links(o.order_id, o.status)
            })
            
        return {"orders": orders_data}
        
    except Exception as e:
        logger.error(f"gRPC List Error: {e}")
        raise HTTPException(status_code=503, detail="Could not fetch order list")

@app.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(order: OrderRequest):
    try:
        session = Session()
        transport = Transport(session=session)
        soap_client = Client(SOAP_SERVICE_URL, transport=transport)
        is_valid = soap_client.service.validateProduct(order.product_id)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Product unavailable")
    except Exception as e:
        logger.error(f"SOAP Validation fail: {e}")

        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=503, detail="Validator unavailable")

    # przetwarzanie grpc
    try:
        stub, channel = get_grpc_stub()
        grpc_req = order_pb2.OrderRequest(
            product_id=order.product_id,
            email=order.email,
            quantity=order.quantity
        )
        response = stub.ProcessOrder(grpc_req)
        channel.close()
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"Order processing failed: {e}")

    # RabbitMQ
    send_notification_rabbitmq(response.order_id, order.email, "created")

    return {
        "order_id": response.order_id,
        "status": response.status,
        "product_id": response.product_id,
        "email": response.email,
        "quantity": response.quantity,
        "_links": get_hateoas_links(response.order_id, response.status)
    }

@app.get("/orders/{order_id}")
async def get_order_details(order_id: str):
    try:
        stub, channel = get_grpc_stub()
        response = stub.GetOrderStatus(order_pb2.OrderIdRequest(order_id=order_id))
        channel.close()
        
        return {
            "order_id": response.order_id,
            "status": response.status,
            "product_id": response.product_id,
            "email": response.email,
            "quantity": response.quantity,
            "_links": get_hateoas_links(response.order_id, response.status)
        }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/orders/{order_id}/status")
async def get_order_status_endpoint(order_id: str):
    return await get_order_details(order_id)

@app.get("/orders/{order_id}/cancel")
async def cancel_order_get_helper(order_id: str):
    return {"message": "Use DELETE method to cancel", "_links": get_hateoas_links(order_id, "unknown")}

@app.delete("/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    try:
        stub, channel = get_grpc_stub()
        response = stub.CancelOrder(order_pb2.OrderIdRequest(order_id=order_id))
        channel.close()
        
        send_notification_rabbitmq(response.order_id, response.email, "cancelled")
        
        return {
            "message": "Order cancelled successfully",
            "order_id": response.order_id,
            "status": response.status,
            "_links": get_hateoas_links(response.order_id, response.status)
        }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
             raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=500, detail="Cancel failed")

@app.get("/")
async def root():
    return {
        "message": "System v2.0",
        "_links": {
            "products": {"href": f"{API_GATEWAY_URL}/products"},
            "create_order": {"href": f"{API_GATEWAY_URL}/orders", "method": "POST"}
        }
    }