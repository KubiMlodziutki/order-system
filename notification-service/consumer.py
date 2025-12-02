import pika
import json
import logging
import time
import os

# log config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

# email sending simulation
# in real scenario we would use smtp etc or something different
def send_email_notification(order_id: str, email: str):
    logger.info(f"📧 Sending email notification...")
    logger.info(f"   To: {email}")
    logger.info(f"   Subject: Order confirmation {order_id}")
    logger.info(f"   Content: Your Order {order_id} has been accepted for processing")
    
    # ssending lag simulation
    time.sleep(1)
    
    logger.info(f"✓ Sent successfully for order {order_id}")

# callback to process message from queue
def callback(ch, method, properties, body):
    try:
        # json parser
        message = json.loads(body)
        
        logger.info(f"Received: {message}")
        
        order_id = message.get("order_id")
        email = message.get("email")
        notification_type = message.get("type", "unknown")
        
        # notification based on type
        if notification_type == "order_confirmation":
            send_email_notification(order_id, email)
        else:
            logger.warning(f"Unknown notifcication type: {notification_type}")
        
        # Procesdsing confirmation
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Message processe dand confirmerd")
        
    except json.JSONDecodeError as e:
        logger.error(f"Parsing JSON error : {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
    except Exception as e:
        logger.error(f"Erorr processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    
    logger.info("Waiting for notify service...")
    
    # wait for rabbit
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            credentials = pika.PlainCredentials('guest', 'guest')
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            
            logger.info(f"Connected with RabbitMQ on {RABBITMQ_HOST}")
            break
            
        except pika.exceptions.AMQPConnectionError:
            retry_count += 1
            logger.warning(f"Cant connect to RabbitMQ, try {retry_count}/{max_retries}")
            time.sleep(2)
    
    if retry_count >= max_retries:
        logger.error("Cant connect to RabbitMQ")
        return
    
    channel.queue_declare(queue='notifications', durable=True)
    
    # orefetch, 1 message at a time
    channel.basic_qos(prefetch_count=1)
    
    # consumer register
    channel.basic_consume(
        queue='notifications',
        on_message_callback=callback
    )
    
    logger.info("⏳ Waiting for messages...")
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("stopping consumer...")
        channel.stop_consuming()
    finally:
        connection.close()
        logger.info("Connection closed")

if __name__ == "__main__":
    main()