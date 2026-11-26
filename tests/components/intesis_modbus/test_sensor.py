"""Tests for the Intesis Modbus sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import INITIALISING_REGISTERS

PREFIX = "sensor.inmbsmhi001r000_"
UNIT_PREFIX = PREFIX + "air_conditioner_"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensors_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Every sensor matches its snapshot."""
    with patch("homeassistant.components.intesis_modbus.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        PREFIX + "undervoltage_time",
        UNIT_PREFIX + "control_lock",
        UNIT_PREFIX + "input_reference_temperature",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensors_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """The sensors few users need have to be enabled by hand."""
    assert hass.states.get(entity_id) is None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


SETPOINT = UNIT_PREFIX + "applied_setpoint"
REFERENCE = UNIT_PREFIX + "input_reference_temperature"
LOCK = UNIT_PREFIX + "control_lock"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_setpoint_reference_and_lock_follow_the_gateway(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The applied setpoint, the input reference and the lock follow each poll."""
    unit = mock_connection.for_unit(1)
    for address, value in {23: 220, 46: 3, 65: 214}.items():
        unit.holding[address] = value
    await _poll(hass, freezer)
    assert hass.states.get(SETPOINT).state == "22.0"
    assert hass.states.get(REFERENCE).state == "21.4"
    assert hass.states.get(LOCK).state == "remote_only"


@pytest.mark.parametrize(
    ("address", "entity_id", "restored"),
    [
        pytest.param(21, SETPOINT, "21.5", id="limits"),
        pytest.param(46, LOCK, "remote_unlock", id="lock"),
        pytest.param(60, REFERENCE, STATE_UNKNOWN, id="temperatures"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_new_sensor_goes_unavailable_alone_with_its_block(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    address: int,
    entity_id: str,
    restored: str,
) -> None:
    """Each sensor follows the block it is read from, and comes back with it."""
    others = {SETPOINT, REFERENCE, LOCK} - {entity_id}
    unit = mock_connection.for_unit(1)
    unit.fail_read(address, IllegalDataAddressError())
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert STATE_UNAVAILABLE not in {hass.states.get(other).state for other in others}
    unit.fail_read(address, None)
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == restored


@pytest.mark.parametrize("registers", [INITIALISING_REGISTERS])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_initialising_gateway_reports_no_setpoint_reference_or_lock(
    hass: HomeAssistant,
) -> None:
    """While the gateway starts up none of the three has a value."""
    assert hass.states.get(SETPOINT).state == STATE_UNKNOWN
    assert hass.states.get(REFERENCE).state == STATE_UNKNOWN
    assert hass.states.get(LOCK).state == STATE_UNKNOWN


@pytest.mark.parametrize("registers", [INITIALISING_REGISTERS])
@pytest.mark.usefixtures("init_integration")
async def test_initialising_gateway_reports_no_values(hass: HomeAssistant) -> None:
    """A gateway that just powered up says so and has no temperatures yet."""
    assert hass.states.get(PREFIX + "error").state == "initialising"
    assert hass.states.get(UNIT_PREFIX + "error_code").state == STATE_UNKNOWN
    for key in ("outdoor_intake_temperature", "return_path_temperature"):
        assert hass.states.get(UNIT_PREFIX + key).state == STATE_UNKNOWN
    assert hass.states.get(UNIT_PREFIX + "operation_time").state == "1234"


@pytest.mark.parametrize("registers", [{11: 7}])
@pytest.mark.usefixtures("init_integration")
async def test_unit_error_shows_the_remote_controller_code(
    hass: HomeAssistant,
) -> None:
    """An error of the air conditioner comes with the code its remote shows."""
    assert hass.states.get(PREFIX + "error").state == "unit_error"
    assert hass.states.get(UNIT_PREFIX + "error_code").state == "E7"


@pytest.mark.parametrize("registers", [{11: 12345}])
@pytest.mark.usefixtures("init_integration")
async def test_unit_error_without_a_remote_controller_code_shows_its_number(
    hass: HomeAssistant,
) -> None:
    """An error the library has no code for is still told apart by its number."""
    assert hass.states.get(PREFIX + "error").state == "unit_error"
    assert hass.states.get(UNIT_PREFIX + "error_code").state == "12345"


@pytest.mark.parametrize("registers", [{9: 32768}])
@pytest.mark.usefixtures("init_integration")
async def test_operation_time_covers_the_whole_register(hass: HomeAssistant) -> None:
    """32768 hours is a reading, not the gateway's initialisation value."""
    assert hass.states.get(UNIT_PREFIX + "operation_time").state == "32768"


@pytest.mark.usefixtures("init_integration")
async def test_failed_block_only_takes_its_own_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Sensors read from a block that stops answering go unavailable alone."""
    assert hass.states.get(UNIT_PREFIX + "outdoor_intake_temperature").state == "12.5"
    mock_connection.for_unit(1).fail_read(60, IllegalDataAddressError())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for key in ("outdoor_intake_temperature", "return_path_temperature"):
        assert hass.states.get(UNIT_PREFIX + key).state == STATE_UNAVAILABLE
    assert hass.states.get(PREFIX + "error").state == "none"
    assert hass.states.get(UNIT_PREFIX + "operation_time").state == "1234"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_unreachable_air_conditioner_is_reported_by_the_error_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The gateway's own sensors stay when it cannot reach the air conditioner."""
    unit = mock_connection.for_unit(1)
    unit.holding[11] = 65535
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(PREFIX + "error").state == "communication_error"
    assert hass.states.get(PREFIX + "undervoltage_time").state == "3"
    for key in (
        "error_code",
        "operation_time",
        "outdoor_intake_temperature",
        "return_path_temperature",
    ):
        assert hass.states.get(UNIT_PREFIX + key).state == STATE_UNAVAILABLE
    unit.holding[11] = 0
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(PREFIX + "error").state == "none"
    assert hass.states.get(UNIT_PREFIX + "outdoor_intake_temperature").state == "12.5"
