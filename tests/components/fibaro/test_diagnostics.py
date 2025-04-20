"""Tests for the diagnostics data provided by the fibaro integration."""

from unittest.mock import Mock

from syrupy import SnapshotAssertion

from homeassistant.components.fibaro import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import TEST_SERIALNUMBER, init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]
    # Act
    await init_integration(hass, mock_config_entry)
    # Assert
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]
    # Act
    await init_integration(hass, mock_config_entry)
    entry = entity_registry.async_get("light.room_1_test_light_3")
    device = device_registry.async_get(entry.device_id)
    # Assert
    assert device
    assert (
        await get_diagnostics_for_device(hass, hass_client, mock_config_entry, device)
        == snapshot
    )


async def test_device_diagnostics_for_hub(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_power_sensor: Mock,
    mock_room: Mock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for the hub."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light, mock_power_sensor]
    # Act
    await init_integration(hass, mock_config_entry)
    device = device_registry.async_get_device({(DOMAIN, TEST_SERIALNUMBER)})
    # Assert
    assert device
    assert (
        await get_diagnostics_for_device(hass, hass_client, mock_config_entry, device)
        == snapshot
    )
