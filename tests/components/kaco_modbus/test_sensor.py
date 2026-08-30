"""Test the KACO Modbus sensor platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from kaco_modbus import KacoInverter
from kaco_modbus.testing import BLUEPLANET_86TL3_ASLEEP
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.components.kaco_modbus.coordinator import SCAN_INTERVAL
from homeassistant.components.kaco_modbus.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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


def test_sensor_descriptions_read_real_fields() -> None:
    """Guard SENSOR_DESCRIPTIONS against a component transcription slip.

    Values are resolved by getattr, so a wrong component name would other-
    wise show up as a permanently empty sensor rather than an error.
    """
    device = KacoInverter(MockModbusConnection().for_unit(1))
    for description in SENSOR_DESCRIPTIONS:
        assert hasattr(device, description.component), (
            f"unknown component {description.component!r}"
        )


async def test_sensor_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the shipped sensors carry the captured inverter's readings."""
    assert hass.states.get(_entity_id(entity_registry, "ac_power")).state == "1000"
    assert (
        hass.states.get(_entity_id(entity_registry, "operating_state")).state == "mppt"
    )
    # Reported in Wh and shown in kWh, so the state is the converted value.
    energy = hass.states.get(_entity_id(entity_registry, "lifetime_energy"))
    assert float(energy.state) == pytest.approx(12187.169)


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


async def test_a_failing_component_does_not_take_out_the_others(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test one unreadable block leaves the rest of the entities alone.

    Components are polled separately, so an entity is unavailable when its
    own component failed, not when any of them did.
    """
    coordinator = init_integration.runtime_data
    # Where the MPPT block landed in this device's discovered model chain.
    assert coordinator.device.models is not None
    mppt = coordinator.device.models.first(160)
    assert mppt is not None
    unit = mock_connection.for_unit(1)

    for address in range(mppt.address, mppt.address + mppt.length):
        unit.fail_read(address, ModbusTimeoutError("slow block"))
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert "mppt" in coordinator.data.failed
    assert hass.states.get(_entity_id(entity_registry, "ac_power")).state == "1000"


async def test_after_dark_the_inverter_reports_a_true_zero(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a sleeping inverter still reports what it genuinely measures.

    A KACO keeps answering after dark rather than going quiet, so nothing
    goes unavailable. Producing nothing really is 0 W, and the lifetime
    total must keep reporting or the Energy dashboard gains a nightly gap.
    """
    connection = MockModbusConnection()
    connection.for_unit(1).load_raw({"holding": dict(BLUEPLANET_86TL3_ASLEEP)})
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.kaco_modbus.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(_entity_id(entity_registry, "ac_power")).state == "0"
    assert (
        hass.states.get(_entity_id(entity_registry, "operating_state")).state
        == "sleeping"
    )
    energy = hass.states.get(_entity_id(entity_registry, "lifetime_energy"))
    assert energy.state != STATE_UNAVAILABLE
    assert float(energy.state) > 12000
