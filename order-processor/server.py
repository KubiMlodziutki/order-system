import grpc
from concurrent import futures
import time
import logging
import uuid
import os
import json
from zeep import Client
from zeep.transports import Transport
from requests import Session

import order_pb2
import order_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrderProcessor")

# config soap
SOAP_SERVICE_URL = os.getenv("SOAP_SERVICE_URL", "http://product-validator:8080/ws/ProductValidator?wsdl")

# database (in-memory)
orders_db = {}

def update_order_status_based_on_time(order):
    if order['status'] == 'cancelled':
        return

    elapsed = time.time() - order['created_at']
    
    if elapsed > 25:
        order['status'] = 'delivered'
    elif elapsed > 10:
        order['status'] = 'on delivery'
    else:
        order['status'] = 'accepted'

class OrderProcessorServicer(order_pb2_grpc.OrderProcessorServicer):
    def GetAllOrders(self, request, context):
        logger.info("Fetching all orders history")
        response_list = []
        
        # Sort
        sorted_orders = sorted(orders_db.values(), key=lambda x: x['created_at'], reverse=True)
        
        for order in sorted_orders:
            # status update
            update_order_status_based_on_time(order)
            
            response_list.append(order_pb2.OrderResponse(
                order_id=order['order_id'],
                status=order['status'],
                product_id=order['product_id'],
                email=order['email'],
                quantity=order['quantity']
            ))
            
        return order_pb2.OrderList(orders=response_list)

    def ProcessOrder(self, request, context):
        logger.info(f"Processing new order for: {request.product_id}")
        
        order_id = f"ORD-{str(uuid.uuid4())[:8].upper()}"
        
        # save to in-memory DB
        orders_db[order_id] = {
            "order_id": order_id,
            "product_id": request.product_id,
            "email": request.email,
            "quantity": request.quantity,
            "status": "accepted",
            "created_at": time.time()
        }
        
        return order_pb2.OrderResponse(
            order_id=order_id,
            status="accepted",
            product_id=request.product_id,
            email=request.email,
            quantity=request.quantity
        )

    def GetOrderStatus(self, request, context):
        order_id = request.order_id
        logger.info(f"Checking status for: {order_id}")
        
        order = orders_db.get(order_id)
        if not order:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details('Order not found')
            return order_pb2.OrderResponse()

        update_order_status_based_on_time(order)

        return order_pb2.OrderResponse(
            order_id=order['order_id'],
            status=order['status'],
            product_id=order['product_id'],
            email=order['email'],
            quantity=order['quantity']
        )

    def CancelOrder(self, request, context):
        order_id = request.order_id
        logger.info(f"Request to cancel: {order_id}")
        
        order = orders_db.get(order_id)
        if not order:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details('Order not found')
            return order_pb2.OrderResponse()

        # state change
        order['status'] = 'cancelled'
        
        return order_pb2.OrderResponse(
            order_id=order['order_id'],
            status=order['status'],
            product_id=order['product_id'],
            email=order['email'],
            quantity=order['quantity']
        )

    def GetAvailableProducts(self, request, context):
        logger.info("Fetching products from SOAP service...")
        products_list = []
        
        try:
            session = Session()
            transport = Transport(session=session)
            client = Client(SOAP_SERVICE_URL, transport=transport)
            
            # ZEEP SOAP call
            soap_response = client.service.getAvailableProducts()
            
            if not soap_response:
                return order_pb2.ProductList(products=[])

            for item in soap_response:
                # create Product protobuf object
                p = order_pb2.Product(
                    id=item.id,
                    name=item.name, 
                    icon=item.icon
                )
                products_list.append(p)
                
        except Exception as e:
            logger.error(f"Error calling SOAP: {e}")
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(f'SOAP Service Unavailable: {str(e)}')
            return order_pb2.ProductList()

        return order_pb2.ProductList(products=products_list)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_pb2_grpc.add_OrderProcessorServicer_to_server(OrderProcessorServicer(), server)
    
    port = "50051"
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"gRPC Server started on port {port}")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()