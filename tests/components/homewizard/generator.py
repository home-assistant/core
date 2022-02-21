"""Helper files for unit tests."""

from unittest.mock import AsyncMock


def get_mock_device(
    serial="aabbccddeeff",
    host="1.2.3.4",
    product_name="P1 meter",
    product_type="HWE-P1",
):
    """Return a mock bridge."""
    mock_device = AsyncMock()
    mock_device.host = host

    mock_device.device.product_name = product_name
    mock_device.device.product_type = product_type
    mock_device.device.serial = serial
    mock_device.device.api_version = "v1"
    mock_device.device.firmware_version = "1.00"

    mock_device.state = None

    mock_device.initialize = AsyncMock()
    mock_device.close = AsyncMock()

    return mock_device
