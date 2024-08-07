"""Test the helper method for writing tests."""

from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.lgthinq import DOMAIN
from homeassistant.components.lgthinq.const import DOMAIN
from homeassistant.components.lgthinq.device import (
    LGDevice,
    async_setup_lg_device,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.json import json_loads
from tests.common import MockConfigEntry, load_fixture

device_file_fn: Callable[[str], str] = lambda device_type: (
    f"{device_type.replace('DEVICE_', '').lower()}_device.json"
)
profile_file_fn: Callable[[str], str] = lambda device_type: (
    f"{device_type.replace('DEVICE_', '').lower()}_profile.json"
)
status_file_fn: Callable[[str], str] = lambda device_type: (
    f"{device_type.replace('DEVICE_', '').lower()}_status.json"
)


def mock_device_info(device_type: str) -> dict[str, Any]:
    """Load a mock device info from json file."""
    return json_loads(load_fixture(device_file_fn(device_type), DOMAIN))


def mock_device_profile(device_type: str) -> dict[str, Any]:
    """Load a mock device profile from json file."""
    return json_loads(load_fixture(profile_file_fn(device_type), DOMAIN))


def mock_device_status(device_type: str) -> dict[str, Any]:
    """Load a mock device status from json file."""
    return json_loads(load_fixture(status_file_fn(device_type), DOMAIN))


def mock_thinq(device_info: dict[str, Any]) -> MagicMock:
    """Create a mock thinq instance."""
    thinq = MagicMock()
    thinq.target_device_info = device_info
    thinq.async_get_device_list = AsyncMock(
        return_value=[thinq.target_device_info]
    )
    thinq.async_get_device_profile = AsyncMock(
        return_value=mock_device_profile(
            device_info.get("deviceInfo").get("deviceType")
        )
    )
    thinq.async_get_device_status = AsyncMock(
        return_value=mock_thinq_api_response()
    )
    return thinq


def mock_thinq_api_response(
    *,
    status: int = 400,
    body: dict = None,
    error_code: str = None,
    error_message: str = None,
) -> MagicMock:
    """Create a mock thinq api response."""
    response = MagicMock()
    response.status = status
    response.body = body
    response.error_code = error_code
    response.error_message = error_message
    return response


async def mock_lg_device(
    hass: HomeAssistant, device_info: dict[str, Any]
) -> LGDevice:
    """Create a mock lg device."""
    return await async_setup_lg_device(
        hass, mock_thinq(device_info), device_info
    )


def get_mock_lg_device_for_type(
    config_entry_thinq: MockConfigEntry, device_type: str
) -> LGDevice | None:
    """Returns a mock lg device for the given type."""
    if not hasattr(config_entry_thinq, "runtime_data"):
        return None

    if not hasattr(config_entry_thinq.runtime_data, "lge_devices"):
        return None

    lge_devices: list[LGDevice] = config_entry_thinq.runtime_data.lge_devices
    for lg_device in lge_devices:
        if lg_device.type == device_type:
            return lg_device

    return None
