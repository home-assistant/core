"""Test for the switchbot_cloud base entity."""

from unittest.mock import patch

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import METER_INFO, configure_integration


async def test_sw_version_cast_to_string(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test the device sw_version is a string when the API returns an int."""
    mock_list_devices.return_value = [METER_INFO]
    mock_get_status.return_value = {"version": 123}

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        await configure_integration(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, METER_INFO.device_id)}
    )
    assert device is not None
    assert device.sw_version == "123"


async def test_sw_version_none_when_missing(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test the device sw_version is None when the API omits the version."""
    mock_list_devices.return_value = [METER_INFO]
    mock_get_status.return_value = {}

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        await configure_integration(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, METER_INFO.device_id)}
    )
    assert device is not None
    assert device.sw_version is None
