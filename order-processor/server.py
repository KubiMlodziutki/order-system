import grpc
from concurrent import futures
import time
import logging
import uuid
import order_pb2
import order_pb2_grpc
import json
from zeep import Client
from zeep.transports import Transport
from requests import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

orders_db = {}

class OrderProcessorServicer(order_pb2_grpc.OrderProcessorServicer):
    
    def ProcessOrder(self, request, context):
        logger.info(f"Tir order processing request:")
        logger.info(f"  Product ID: {request.product_id}")
        logger.info(f"  Email: {request.email}")
        logger.info(f"  Quantity: {request.quantity}")
        
        order_id = f"ORD-{str(uuid.uuid4())[:8].upper()}"
        
        orders_db[order_id] = {
            "product_id": request.product_id,
            "email": request.email,
            "quantity": request.quantity,
            "status": "processing",
            "timestamp": time.time()
        }
        
        logger.info(f"Order processed successfylly, ID: {order_id}")
        logger.info(f"Databasehas {len(orders_db)} Orders")
        
        # Zwrócenie odpowiedzi
        return order_pb2.OrderResponse(
            order_id=order_id,
            status="accepted"
        )


def GetProducts_generic(unused_request, context):
    # Call the SOAP ProductValidator to get list of available product IDs
    try:
        session = Session()
        session.timeout = 10
        transport = Transport(session=session)
        soap_client = Client('http://product-validator:8080/ws/ProductValidator?wsdl', transport=transport)
        ids = soap_client.service.getAvailableProducts()
        # enrich products with simple metadata (name/icon) - can be replaced with real store data
        name_map = {
            'PROD-001': ('Mocbook Stone', '💻'),
            'PROD-002': ('YouPhone X', '📱'),
            'PROD-003': ('Tablet Pro', '📱'),
            'PROD-004': ('SmartWatch', '⌚'),
            'PROD-005': ('Camera Max', '📷'),
            'PROD-007': ('Just headphones', '🎧')
        }

        products = []
        for pid in ids:
            name, icon = name_map.get(pid, (pid, '📦'))
            products.append({'id': pid, 'name': name, 'icon': icon})

        payload = json.dumps({'products': products}).encode('utf-8')
        return payload
    except Exception as e:
        context.set_code(grpc.StatusCode.UNAVAILABLE)
        context.set_details(f'Product validator unavailable: {e}')
        return b''

def serve():
    
    # threadpool server creation
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # adding service to server
    order_pb2_grpc.add_OrderProcessorServicer_to_server(
        OrderProcessorServicer(), server
    )

    # add a generic handler for GetProducts that returns JSON bytes
    rpc_method_handlers = {
        'GetProducts': grpc.unary_unary_rpc_method_handler(
            GetProducts_generic,
            request_deserializer=lambda x: x,
            response_serializer=lambda x: x
        )
    }

    generic_handler = grpc.method_handlers_generic_handler(
        'order.OrderProcessor', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    
    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    
    logger.info(f"Serwer gRPC running on {port}")
    
    server.start()
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping server...")
        server.stop(0)

if __name__ == "__main__":
    serve()