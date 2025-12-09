package com.validator;

import jakarta.jws.WebService;
import java.util.Arrays;
import java.util.List;
import java.util.logging.Logger;

@WebService(endpointInterface = "com.validator.ProductValidator")
public class ProductValidatorImpl implements ProductValidator {
    
    private static final Logger logger = Logger.getLogger(ProductValidatorImpl.class.getName());
    
    // simulation of available list
    private static final List<String> AVAILABLE_PRODUCTS = Arrays.asList(
        "PROD-001", "PROD-002", "PROD-003", "PROD-004", "PROD-005"
    );
    
    @Override
    public boolean validateProduct(String productId) {
        logger.info("Product vaidation: " + productId);
        
        // availability check
        boolean isAvailable = AVAILABLE_PRODUCTS.contains(productId);
        
        logger.info("Product " + productId + " - available: " + isAvailable);
        
        return isAvailable;
    }

    @Override
    public String[] getAvailableProducts() {
        logger.info("Returning available products from validator");
        return AVAILABLE_PRODUCTS.toArray(new String[0]);
    }
}