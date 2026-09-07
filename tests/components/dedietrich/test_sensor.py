"""Test the De Dietrich Diematic Modbus sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dedietrich.const import (
    DEFAULT_UNIT_ID,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all sensors match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("register", "value", "circuit_key", "expect_entity"),
    [
        pytest.param(
            614, 210, "circuit_a_room_temperature", True, id="circuit_a_present"
        ),
        pytest.param(
            614, 0xFFFF, "circuit_a_room_temperature", False, id="circuit_a_absent"
        ),
        pytest.param(
            616, 205, "circuit_b_room_temperature", True, id="circuit_b_present"
        ),
        pytest.param(
            616, 0xFFFF, "circuit_b_room_temperature", False, id="circuit_b_absent"
        ),
    ],
)
async def test_circuit_sensor_exists_fn(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    register: int,
    value: int,
    circuit_key: str,
    expect_entity: bool,
) -> None:
    """Test a circuit's room-temperature sensor follows its circuit_*_present."""
    mock_connection.for_unit(DEFAULT_UNIT_ID).holding[register] = value
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dedietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_{circuit_key}"
    )
    assert (entity_id is not None) is expect_entity


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModbusTimeoutError("stuck"), id="timeout"),
        pytest.param(ModbusConnectionError("dead"), id="connection"),
    ],
)
async def test_sensor_unavailable_on_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    error: ModbusError,
) -> None:
    """Test a sensor becomes unavailable when a poll fails, then recovers."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{init_integration.entry_id}_outdoor_temperature"
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state != "unavailable"

    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    unit.fail_requests(error)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == "unavailable"

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state != "unavailable"
