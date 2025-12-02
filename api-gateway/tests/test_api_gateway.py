def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "_links" in response.json()

def test_list_orders(client):
    response = client.get("/orders")
    assert response.status_code == 200
    assert "orders" in response.json()

def test_get_order(client):
    response = client.get("/orders/ORD-123")
    assert response.status_code == 200
    assert response.json()["order_id"] == "ORD-123"

def test_create_order_with_mocks(client, mock_soap, mock_grpc, mock_rabbitmq):
    response = client.post("/orders", json={
        "product_id": "PROD-001",
        "email": "test@example.com",
        "quantity": 1
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["order_id"] == "ORD-TEST123"
    assert data["status"] == "accepted"
    assert data["product_id"] == "PROD-001"
    assert data["email"] == "test@example.com"
    
    assert "order_id" in data
    assert "status" in data

    mock_soap.assert_called_once_with("PROD-001")
    mock_grpc.assert_called_once()
    mock_rabbitmq.assert_called_once()

def test_cancel_order(client):
    response = client.delete("/orders/ORD-123/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"