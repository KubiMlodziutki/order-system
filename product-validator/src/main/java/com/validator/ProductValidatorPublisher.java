package com.validator;

import jakarta.xml.ws.Endpoint;
import java.util.logging.Logger;

public class ProductValidatorPublisher {
    
    private static final Logger logger = Logger.getLogger(ProductValidatorPublisher.class.getName());
    
    public static void main(String[] args) {
        // bind the server to all interfaces, but advertise a container-reachable hostname
        String bindUrl = "http://0.0.0.0:8080/ws/ProductValidator";
        String wsdlUrl = "http://product-validator:8080/ws/ProductValidator?wsdl";

        logger.info("Service SOAP on address: " + bindUrl);

        Endpoint.publish(bindUrl, new ProductValidatorImpl());

        logger.info("SOAP Service ran successfuly");
        logger.info("WSDL available on: " + wsdlUrl);
        
        try {
            Thread.currentThread().join();
        } catch (InterruptedException e) {
            logger.severe("Service stopped: " + e.getMessage());
        }
    }
}