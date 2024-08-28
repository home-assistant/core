"""Test the helper method for writing tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.lgthinq.const import DOMAIN
from homeassistant.util.json import json_loads

from tests.common import load_fixture


def get_device_file_name(device_type: str) -> str:
    """Return the device info filename for the device type."""
    return f"{device_type.replace('DEVICE_', '').lower()}_device.json"


def get_profile_file_name(device_type: str) -> str:
    """Return the device profile filename for the device type."""
    return f"{device_type.replace('DEVICE_', '').lower()}_profile.json"


def get_status_file_name(device_type: str) -> str:
    """Return the device status filename for the device type."""
    return f"{device_type.replace('DEVICE_', '').lower()}_status.json"


def mock_device_info(device_type: str) -> dict[str, Any]:
    """Load a mock device info from json file."""
    info = json_loads(load_fixture(get_device_file_name(device_type), DOMAIN))
    assert isinstance(info, dict)
    return info


def mock_device_profile(device_type: str) -> dict[str, Any]:
    """Load a mock device profile from json file."""
    info = json_loads(load_fixture(get_profile_file_name(device_type), DOMAIN))
    assert isinstance(info, dict)
    return info


def mock_device_status(device_type: str) -> dict[str, Any]:
    """Load a mock device status from json file."""
    info = json_loads(load_fixture(get_status_file_name(device_type), DOMAIN))
    assert isinstance(info, dict)
    return info


def mock_thinq(device_info: dict[str, Any]) -> MagicMock:
    """Create a mock thinq instance."""
    assert device_info
    device_data = device_info.get("deviceInfo")

    assert device_data
    assert isinstance(device_data, dict)
    device_type = device_data.get("deviceType")

    assert device_type
    assert isinstance(device_type, str)

    thinq = MagicMock()
    thinq.target_device_info = device_info
    thinq.async_get_device_list = AsyncMock(return_value=[thinq.target_device_info])
    thinq.async_get_device_profile = AsyncMock(
        return_value=mock_device_profile(device_type)
    )
    return thinq


def mock_thinq_api_response(
    *,
    status: int = 400,
    body: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> MagicMock:
    """Create a mock thinq api response."""
    response = MagicMock()
    response.status = status
    response.body = body
    response.error_code = error_code
    response.error_message = error_message
    return response
