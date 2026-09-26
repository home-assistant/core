"""Test the De Dietrich sensor platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.de_dietrich.const import (
    DEFAULT_UNIT_ID,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all sensors match their snapshot."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    assert device is not None
    assert device.name == "De Dietrich"
    assert device.model is None
    assert device.manufacturer == "De Dietrich"
    assert device.sw_version == "100"
    sensor_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
        if entry.domain == SENSOR_DOMAIN
    ]
    assert sensor_entries
    for entity_entry in sensor_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_entry.disabled_by is None, "Please enable all entities."
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_diagnostic_entities_disabled_by_default(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostic sensors are disabled by default."""
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    disabled = {
        entry.unique_id.removeprefix(f"{init_integration.entry_id}_")
        for entry in entries
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }
    assert disabled == {
        "calc_boiler_temperature",
        "exhaust_temperature",
        "fan_speed",
        "ionization_current",
    }


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


@pytest.mark.usefixtures("init_integration")
async def test_sensor_partial_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a failed circuit becomes unavailable while other readings update."""
    circuit_id = "sensor.de_dietrich_heating_circuit_a_room_temperature"
    outdoor_id = "sensor.de_dietrich_outdoor_temperature"
    assert hass.states.get(circuit_id).state == "21.0"
    assert hass.states.get(outdoor_id).state == "5.0"

    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    unit.fail_read(654, ModbusTimeoutError("circuit unavailable"))
    unit.holding[601] = 60
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(circuit_id).state == "unavailable"
    assert hass.states.get(outdoor_id).state == "6.0"

    unit.fail_read(654, None)
    unit.holding[614] = 220
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(circuit_id).state == "22.0"
    assert hass.states.get(outdoor_id).state == "6.0"
