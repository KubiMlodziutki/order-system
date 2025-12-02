package com.validator;

import jakarta.xml.ws.Endpoint;
import java.util.logging.Logger;

public class ProductValidatorPublisher {
    
    private static final Logger logger = Logger.getLogger(ProductValidatorPublisher.class.getName());
    
    public static void main(String[] args) {
        String url = "http://0.0.0.0:8080/ws/ProductValidator";
        
        logger.info("Service SOAP on address: " + url);
        
        Endpoint.publish(url, new ProductValidatorImpl());
        
        logger.info("SOAP Service ran successfuly");
        logger.info("WSDL available on: " + url + "?wsdl");
        
        try {
            Thread.currentThread().join();
        } catch (InterruptedException e) {
            logger.severe("Service stopped: " + e.getMessage());
        }
    }
}