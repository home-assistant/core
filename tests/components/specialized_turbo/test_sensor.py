"""Tests for Specialized Turbo sensor entities."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.specialized_turbo.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import (
    MOCK_ADDRESS_FORMATTED,
    TCX_SERVICE_INFO,
    MockLibrary,
    make_populated_snapshot,
)

from tests.common import MockConfigEntry, snapshot_platform


def _entity_id(entity_registry: er.EntityRegistry, key: str) -> str:
    """Return an entity ID from its stable integration unique ID."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_ADDRESS_FORMATTED}_{key}",
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor metadata and values."""
    mock_library.monitor.snapshot = make_populated_snapshot()
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_sensors_unavailable_before_first_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors remain unavailable before telemetry arrives."""
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    state = hass.states.get(_entity_id(entity_registry, "battery_charge_percent"))
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_notification_updates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a library notification updates entity state."""
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)
    updated = make_populated_snapshot()

    callback = mock_library.monitor.on_update
    assert callable(callback)
    callback(MagicMock(), updated)
    await hass.async_block_till_done()

    battery = hass.states.get(_entity_id(entity_registry, "battery_charge_percent"))
    speed = hass.states.get(_entity_id(entity_registry, "speed"))
    assist = hass.states.get(_entity_id(entity_registry, "assist_level"))
    assert battery is not None
    assert speed is not None
    assert assist is not None
    assert battery.state == "85"
    assert speed.state == "25.5"
    assert assist.state == "trail"


async def test_disconnect_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a library disconnect marks entities unavailable."""
    mock_library.monitor.snapshot = make_populated_snapshot()
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)
    battery_entity_id = _entity_id(entity_registry, "battery_charge_percent")
    battery = hass.states.get(battery_entity_id)
    assert battery is not None
    assert battery.state == "85"

    disconnect_callback = mock_library.connection_constructor.call_args.kwargs[
        "disconnect_callback"
    ]
    mock_library.connection.is_connected = False
    disconnect_callback(mock_library.connection)
    await hass.async_block_till_done()

    battery = hass.states.get(battery_entity_id)
    assert battery is not None
    assert battery.state == STATE_UNAVAILABLE


async def test_unknown_assist_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unknown assist value produces an unknown entity state."""
    snapshot = make_populated_snapshot()
    snapshot.motor.assist_level = 99
    mock_library.monitor.snapshot = snapshot
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    assist = hass.states.get(_entity_id(entity_registry, "assist_level"))
    assert assist is not None
    assert assist.state == STATE_UNKNOWN
