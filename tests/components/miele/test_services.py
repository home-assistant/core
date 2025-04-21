"""Tests the services provided by the miele integration."""

from unittest.mock import MagicMock

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.miele.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration

from tests.common import MockConfigEntry

TEST_APPLIANCE = "Dummy_Appliance_1"


async def test_services(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the custom services are correct."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})
    await hass.services.async_call(
        DOMAIN,
        "set_program",
        {
            CONF_DEVICE_ID: device.id,
            "program_id": 24,
        },
        blocking=True,
    )
    mock_miele_client.set_program.assert_called_once()

    await hass.services.async_call(
        DOMAIN,
        "set_program",
        {
            CONF_DEVICE_ID: device.id,
            "program_id": 24,
            "duration": 75,
            "temperature": 195,
        },
        blocking=True,
    )
    assert mock_miele_client.set_program.call_count == 2


async def test_service_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service errors."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})

    # Test http error
    mock_miele_client.set_program.side_effect = ClientResponseError("TestInfo", "test")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_program",
            {"device_id": device.id, "program_id": 1},
            blocking=True,
        )
    assert mock_miele_client.set_program.call_count == 1
