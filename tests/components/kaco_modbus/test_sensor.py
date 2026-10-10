"""Test the KACO Modbus sensor platform."""

from freezegun.api import FrozenDateTimeFactory
from kaco_modbus.const import INVERTER_MODEL_ID
from kaco_modbus.testing import BLUEPLANET_86TL3, BLUEPLANET_86TL3_ASLEEP
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.components.kaco_modbus.coordinator import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL, model_registers

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# The readings someone adds this integration to get, as opposed to the detail
# ones that stay disabled until they are asked for.
PRIMARY_SENSORS = {
    "ac_current",
    "ac_power",
    "dc_power",
    "lifetime_energy",
    "operating_state",
    "temperature",
}


def _entity_id(entity_registry: er.EntityRegistry, key: str) -> str:
    """Look the entity up by unique id rather than by a guessed slug."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_{key}"
    )
    assert entity_id is not None, f"{key} was not created"
    return entity_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_only_primary_readings_are_enabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the detail readings are left for a user to opt into."""
    enabled = {
        entry.unique_id.removeprefix(f"{MOCK_SERIAL}_")
        for entry in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
        if entry.disabled_by is None
    }
    assert enabled == PRIMARY_SENSORS


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("key", "expected"),
    [
        pytest.param("ac_power", "1000", id="ac_power"),
        pytest.param("ac_current", "4.84", id="ac_current"),
        pytest.param("operating_state", "mppt", id="operating_state"),
        pytest.param("power_factor", "1.0", id="power_factor"),
        pytest.param("frequency", "49.944", id="frequency"),
        pytest.param("temperature", "46.9", id="temperature"),
        pytest.param("voltage_l1", "226.5", id="voltage_l1"),
        pytest.param("current_l1", "1.64", id="current_l1"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    key: str,
    expected: str,
) -> None:
    """Test the sensors carry the captured inverter's readings."""
    assert hass.states.get(_entity_id(entity_registry, key)).state == expected


async def test_lifetime_energy_is_converted_to_kilowatt_hours(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the total is reported in Wh and shown in kWh."""
    energy = hass.states.get(_entity_id(entity_registry, "lifetime_energy"))
    assert float(energy.state) == pytest.approx(12187.169)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("register_image", [BLUEPLANET_86TL3_ASLEEP])
@pytest.mark.parametrize(
    "key", ["frequency", "power_factor", "temperature", "voltage_l1"]
)
async def test_readings_it_stops_taking_are_withheld(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    key: str,
) -> None:
    """Test a reading the inverter parks at zero after dark reads unknown.

    These come from the device, which gates them on the operating state,
    rather than off the raw registers: asleep the block claims 0.0 Hz for a
    live grid, 0.0 degC for a warm cabinet, 0.0 V for live mains, and a power
    factor of 1.00 with no current flowing.
    """
    assert hass.states.get(_entity_id(entity_registry, key)).state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("register_image", [BLUEPLANET_86TL3_ASLEEP])
@pytest.mark.parametrize(
    "key", ["ac_power", "ac_current", "apparent_power", "dc_power", "current_l1"]
)
async def test_genuine_zeros_are_still_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    key: str,
) -> None:
    """Test producing nothing really is zero, and is not withheld."""
    assert float(hass.states.get(_entity_id(entity_registry, key)).state) == 0


@pytest.mark.parametrize("register_image", [BLUEPLANET_86TL3_ASLEEP])
async def test_the_lifetime_total_survives_the_night(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test a sleeping inverter keeps reporting what it has produced.

    A KACO keeps answering after dark rather than going quiet, so nothing
    goes unavailable and the Energy dashboard gains no nightly gap.
    """
    assert (
        hass.states.get(_entity_id(entity_registry, "operating_state")).state
        == "sleeping"
    )
    energy = hass.states.get(_entity_id(entity_registry, "lifetime_energy"))
    assert float(energy.state) == pytest.approx(12187.710)


async def test_sensors_go_unavailable_when_the_link_drops(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a silent inverter takes its sensors unavailable, then recovers."""
    power = _entity_id(entity_registry, "ac_power")
    unit = mock_connection.for_unit(1)

    unit.fail_requests(ModbusTimeoutError("asleep"))
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(power).state == STATE_UNAVAILABLE

    # Recovery must not need a reload: every request connects first.
    unit.fail_requests(None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(power).state == "1000"


async def test_an_unreadable_block_takes_its_sensors_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a partial poll, where one block fails and the others answer.

    A different path from a dead link: the poll still succeeds, so the entry
    stays loaded, and it is the per-component check that takes these entities
    unavailable. That the *other* components are unaffected is not observable
    until a second component has entities of its own.
    """
    power = _entity_id(entity_registry, "ac_power")
    assert hass.states.get(power).state == "1000"

    unit = mock_connection.for_unit(1)
    for address in model_registers(BLUEPLANET_86TL3, INVERTER_MODEL_ID):
        unit.fail_read(address, ModbusTimeoutError("slow block"))
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(power).state == STATE_UNAVAILABLE
    assert init_integration.state is ConfigEntryState.LOADED
