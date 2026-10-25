"""Tests for the Cync integration setup."""

from unittest.mock import MagicMock

from pycync import CyncPlug
from pycync.devices.device_types import DeviceType

from homeassistant.components.cync.const import DOMAIN
from homeassistant.components.cync.coordinator import CyncCoordinator
from homeassistant.components.cync.entity import CyncBaseEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_outlet_registry_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    cync_client: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the base entity registers outlets sharing a cloud ID independently."""
    mock_config_entry.add_to_hass(hass)
    coordinator = CyncCoordinator(hass, mock_config_entry, cync_client)
    outlets = [
        CyncPlug(
            is_online=True,
            wifi_connected=True,
            device_id=1234,
            mesh_device_id=mesh_id,
            home_id=10000,
            name="Outdoor outlet",
            device_type_id=67,
            device_type=DeviceType.PLUG,
            mac_address="ABCDEF123456",
            product_id="product123",
            authorize_code="abcd_code",
        )
        for mesh_id in (1006, 2006)
    ]
    cync_client.get_devices.return_value = outlets
    await coordinator.async_refresh()

    for outlet in outlets:
        entity = CyncBaseEntity(outlet, coordinator)
        device = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id, **entity.device_info
        )
        entity_registry.async_get_or_create(
            Platform.SWITCH,
            DOMAIN,
            entity.unique_id,
            config_entry=mock_config_entry,
            device_id=device.id,
        )

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries} == {"10000-1006", "10000-2006"}
    assert len({entry.device_id for entry in entries}) == 2
    assert set(coordinator.data) == {"10000-1006", "10000-2006"}


async def test_setup_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an existing version 1 config entry sets up without migration."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.version == 1

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
