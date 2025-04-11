import pytest
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def pytest_addoption(parser):
    parser.addoption(
        "--run-integration", 
        action="store_true", 
        default=False, 
        help="run integration tests"
    )

def pytest_configure(config):
    config.addinivalue_line("markers", 
                            "integration: mark test as integration test")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        # --run-integration given: do not skip integration tests
        return
    
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
