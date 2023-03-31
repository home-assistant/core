"""Helper files for unit tests."""

from unittest.mock import AsyncMock

from homewizard_energy.features import Features
from homewizard_energy.models import Data, Device


def get_mock_device(
    serial="aabbccddeeff",
    host="1.2.3.4",
    product_name="P1 meter",
    product_type="HWE-P1",
    firmware_version="1.00",
):
    """Return a mock bridge."""
    mock_device = AsyncMock()
    mock_device.host = host

    mock_device.device = AsyncMock(
        return_value=Device(
            product_name=product_name,
            product_type=product_type,
            serial=serial,
            api_version="V1",
            firmware_version=firmware_version,
        )
    )
    mock_device.data = AsyncMock(return_value=Data.from_dict({}))
    mock_device.state = AsyncMock(return_value=None)
    mock_device.system = AsyncMock(return_value=None)
    mock_device.features = AsyncMock(
        return_value=Features(product_type, firmware_version)
    )

    mock_device.close = AsyncMock()

    return mock_device
