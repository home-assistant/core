"""Test init methods."""

from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.fibaro.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import TEST_SERIALNUMBER, init_integration


async def test_migrate_device_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fibaro_client: Mock,
) -> None:
    """Test migration converts integer Fibaro device identifiers to strings."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, 3)},  # type: ignore[arg-type]
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    migrated_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "3"), mock_config_entry.entry_id
    )
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, "3")}
    assert mock_config_entry.version == 2


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
        (DOMAIN, str(mock_light.fibaro_id)), mock_config_entry.entry_id
    )
    assert hub_device is not None
    assert light_device is not None
    assert light_device.via_device_id == hub_device.id


@pytest.mark.parametrize(
    ("fibaro_id", "removable"),
    [
        pytest.param(3, False, id="served_by_controller"),
        pytest.param(999, True, id="no_longer_served"),
    ],
)
async def test_remove_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
    fibaro_id: int,
    removable: bool,
) -> None:
    """Test only devices the controller no longer serves can be removed."""
    assert await async_setup_component(hass, "config", {})
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]
    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, str(fibaro_id))},
    )
    client = await hass_ws_client(hass)

    response = await client.remove_device(device.id)

    assert response["success"] is removable
