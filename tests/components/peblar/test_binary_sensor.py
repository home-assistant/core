"""Tests for the Peblar binary sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("init_integration", [Platform.BINARY_SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the binary sensors entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure all entities are correctly assigned to the Peblar EV charger
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "23-45-A4O-MOF"), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize("init_integration", [Platform.BINARY_SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_socket_lock(hass: HomeAssistant) -> None:
    """Test the socket lock reports in the lock device class polarity.

    The charger calls an unlocked socket LockState false, while the lock
    device class calls an unlocked lock on. The fixture is unlocked.
    """
    state = hass.states.get("binary_sensor.peblar_ev_charger_socket_lock")
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize("mock_peblar", [{"HwHasSocket": False}], indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.BINARY_SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_socket_lock_absent_without_socket(hass: HomeAssistant) -> None:
    """A charger with a fixed cable has no socket lock to report."""
    assert hass.states.get("binary_sensor.peblar_ev_charger_socket_lock") is None
