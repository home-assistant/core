"""Tests for the Synology SRM device tracker platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.device_tracker import (
    DEFAULT_CONSIDER_HOME,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.synology_srm.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent

from . import DEVICE_1, DEVICE_2, DEVICE_SPARSE

from tests.common import MockConfigEntry, async_fire_time_changed


async def _enable_and_reload(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    unique_id: str,
) -> str:
    """Enable the auto-disabled scanner entity for `unique_id` and reload the entry.

    ScannerEntity defaults to disabled when there's no companion device_entry to attach to.
    Tests have to enable explicitly before they can observe states.
    """
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "device_tracker", "synology_srm", unique_id
    )
    assert entity_id is not None
    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    return entity_id


async def test_entity_connected_attributes_and_icon(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A freshly-scanned device is connected, exposes aliased attributes, and uses the connect icon."""
    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_1]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = await _enable_and_reload(hass, mock_config_entry, "aa:bb:cc:dd:ee:01")

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "home"
    assert state.attributes["icon"] == "mdi:lan-connect"
    assert state.attributes["is_banned"] is False
    assert state.attributes["is_parental_controlled"] is False
    assert state.attributes["signal_strength"] == -52
    assert state.attributes["transfer_rx_rate"] == 100
    assert state.attributes["transfer_tx_rate"] == 200

    # last_activity is a property on the entity, not auto-included in state attrs.
    component: EntityComponent = hass.data[DEVICE_TRACKER_DOMAIN]
    entity = next(e for e in component.entities if e.unique_id == "aa:bb:cc:dd:ee:01")
    assert entity.last_activity is not None


async def test_entity_disconnect_wipes_attributes_and_swaps_icon(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Once last_activity ages past consider_home, the entity goes not_home with no attributes and a disconnect icon."""
    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_1]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = await _enable_and_reload(hass, mock_config_entry, "aa:bb:cc:dd:ee:01")

    mock_synology_client.core.get_network_nsm_device.return_value = []
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "not_home"
    assert state.attributes["icon"] == "mdi:lan-disconnect"
    assert "signal_strength" not in state.attributes
    assert "is_banned" not in state.attributes


async def test_entity_handles_missing_optional_fields(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device with only MAC (no hostname, no ip_addr) loads cleanly."""
    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_SPARSE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = await _enable_and_reload(hass, mock_config_entry, "aa:bb:cc:dd:ee:03")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "home"

    component: EntityComponent = hass.data[DEVICE_TRACKER_DOMAIN]
    entity = next(e for e in component.entities if e.unique_id == "aa:bb:cc:dd:ee:03")
    assert entity.hostname is None
    assert entity.ip_address is None


async def test_new_device_appears_after_initial_setup(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Devices that show up on a later scan get their own ScannerEntity registered."""
    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_1]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "device_tracker", "synology_srm", "aa:bb:cc:dd:ee:02"
        )
        is None
    )

    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_1, DEVICE_2]
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        registry.async_get_entity_id(
            "device_tracker", "synology_srm", "aa:bb:cc:dd:ee:02"
        )
        is not None
    )
