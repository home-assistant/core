"""Fixtures for mocking pyiskra's different protocols.

Fixtures:
- `mock_pyiskra_rest`: Mock pyiskra Rest API protocol.
- `mock_pyiskra_modbus`: Mock pyiskra Modbus protocol.
"""

from unittest.mock import patch

import pytest

from .const import PQ_MODEL, SERIAL, SG_MODEL


class MockBasicInfo:
    """Mock BasicInfo class."""

    def __init__(self, model) -> None:
        """Initialize the mock class."""
        self.serial = SERIAL
        self.model = model
        self.description = "Iskra mock device"
        self.location = "imagination"
        self.sw_ver = "1.0.0"


@pytest.fixture
def mock_pyiskra_rest():
    """Mock Iskra API authenticate with Rest API protocol."""

    with patch(
        "pyiskra.adapters.RestAPI.RestAPI.get_basic_info",
        return_value=MockBasicInfo(model=SG_MODEL),
    ) as basic_info_mock:
        yield basic_info_mock


@pytest.fixture
def mock_pyiskra_modbus():
    """Mock Iskra API authenticate with Rest API protocol."""

    with patch(
        "pyiskra.adapters.Modbus.Modbus.get_basic_info",
        return_value=MockBasicInfo(model=PQ_MODEL),
    ) as basic_info_mock:
        yield basic_info_mock
