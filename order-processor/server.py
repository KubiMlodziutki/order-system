import grpc
from concurrent import futures
import time
import logging
import uuid
import order_pb2
import order_pb2_grpc

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

def serve():
    
    # threadpool server creation
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # adding service to server
    order_pb2_grpc.add_OrderProcessorServicer_to_server(
        OrderProcessorServicer(), server
    )
    
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