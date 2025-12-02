package com.validator;

import jakarta.jws.WebMethod;
import jakarta.jws.WebParam;
import jakarta.jws.WebService;

@WebService
public interface ProductValidator {
    
    @WebMethod
    boolean validateProduct(@WebParam(name = "productId") String productId);
}