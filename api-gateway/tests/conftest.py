import pytest
import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
sys.path.insert(0, app_dir)


try:
    import order_pb2
    import order_pb2_grpc
except ImportError:
    sys.modules['order_pb2'] = MagicMock()
    sys.modules['order_pb2_grpc'] = MagicMock()

from app import app

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: ingtegration tests")

@pytest.fixture(scope="session", autouse=True)
def setup_mocks(request):
    marker_expr = request.config.getoption("-m")
    
    if marker_expr and "integration" in marker_expr:
        yield
    else:
        grpc_mock = MagicMock()
        with patch.dict(sys.modules, {'order_pb2': grpc_mock, 'order_pb2_grpc': grpc_mock}):
            yield

# test client
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client

# patching fixture for unit testing
@pytest.fixture
def mock_soap():
    with patch('app.validate_product_soap') as mock:
        mock.return_value = True
        yield mock

@pytest.fixture
def mock_grpc():
    with patch('app.process_order_grpc') as mock:
        mock.return_value = "ORD-TEST123"
        yield mock

@pytest.fixture
def mock_rabbitmq():
    with patch('app.send_notification_rabbitmq') as mock:
        yield mock