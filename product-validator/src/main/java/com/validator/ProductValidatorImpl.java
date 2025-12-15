package com.validator;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import jakarta.jws.WebService;
import java.io.File;
import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.logging.Logger;

@WebService(endpointInterface = "com.validator.ProductValidator")
public class ProductValidatorImpl implements ProductValidator {
    
    private static final Logger logger = Logger.getLogger(ProductValidatorImpl.class.getName());
    private List<Product> productsCache;
    
    public ProductValidatorImpl() {
        loadProducts();
    }


    private void loadProducts() {
        ObjectMapper mapper = new ObjectMapper();
        try {
            // path inside the container
            File file = new File("/app/data/products.json");
            if (file.exists()) {
                productsCache = mapper.readValue(file, new TypeReference<List<Product>>(){});
                logger.info("Loaded " + productsCache.size() + " products from JSON");
            } else {
                logger.warning("products.json not found at " + file.getAbsolutePath());
                productsCache = Collections.emptyList();
            }
        } catch (IOException e) {
            logger.severe("Error reading JSON: " + e.getMessage());
            productsCache = Collections.emptyList();
        }
    }
    
    @Override
    public boolean validateProduct(String productId) {
        // availability check against cached products
        return productsCache.stream()
                .anyMatch(p -> p.getId().equals(productId));
    }

    @Override
    public Product[] getAvailableProducts() {
        return productsCache.toArray(new Product[0]);
    }
}