"""Test init methods."""

from unittest.mock import Mock, patch

from homeassistant.components.fibaro.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_SERIALNUMBER, init_integration

from tests.common import MockConfigEntry


async def test_unload_integration(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test unload integration stops state listener."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)
        # Act
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Assert
        assert mock_fibaro_client.unregister_update_handler.call_count == 1


async def test_load_integration_links_device_to_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test load integration sets via_device_id for a light device to the hub device."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    # Act
    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)

    # Assert
    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_SERIALNUMBER), mock_config_entry.entry_id
    )
    light_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_light.fibaro_id), mock_config_entry.entry_id
    )
    assert hub_device is not None
    assert light_device is not None
    assert light_device.via_device_id == hub_device.id
