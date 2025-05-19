"""Test the Zimi light entity."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import INPUT_HOST, INPUT_MAC, INPUT_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api():
    """Mock the API."""
    with patch("homeassistant.components.zimi.async_connect_to_controller") as mock:
        mock_api = mock.return_value

        mock_api.connect.return_value = True
        mock_api.mac = INPUT_MAC
        mock_api.brand = "Zimi"
        mock_api.network_name = "Test Network"
        mock_api.firmware_version = "1.0.0"

        mock_device = MagicMock()
        mock_device.identifier = "test-device-id"
        mock_device.room = "Living Room"
        mock_device.name = "Light Name"

        mock_manfacture_info = MagicMock()
        mock_manfacture_info.identifier = "test-hub-id"
        mock_manfacture_info.manufacturer = "Zimi"
        mock_manfacture_info.model = "Zimi Hub"
        mock_manfacture_info.name = "Zimi Hub"
        mock_manfacture_info.hwVersion = "1.0"
        mock_manfacture_info.firmwareVersion = "1.0.0"

        mock_device.manufacture_info = mock_manfacture_info

        mock_api.lights = [mock_device]

        yield mock


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the specified Zimi platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: INPUT_HOST, CONF_PORT: INPUT_PORT}
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.zimi.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry


async def test_light_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests lights are registered in the entity registry."""

    await setup_platform(hass, Platform.LIGHT)

    entity = entity_registry.entities["light.zimi_hub_light_name"]
    assert entity.unique_id == "test-device-id"
