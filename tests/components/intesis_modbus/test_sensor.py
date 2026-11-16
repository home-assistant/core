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


@pytest.mark.usefixtures("init_integration")
async def test_undervoltage_time_is_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The gateway's undervoltage counter has to be enabled by hand."""
    entity_id = PREFIX + "undervoltage_time"
    assert hass.states.get(entity_id) is None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("registers", [INITIALISING_REGISTERS])
@pytest.mark.usefixtures("init_integration")
async def test_initialising_gateway_reports_no_values(hass: HomeAssistant) -> None:
    """A gateway that just powered up says so and has no values yet."""
    assert hass.states.get(PREFIX + "error").state == "initialising"
    for key in (
        "error_code",
        "operation_time",
        "outdoor_intake_temperature",
        "return_path_temperature",
    ):
        assert hass.states.get(PREFIX + key).state == STATE_UNKNOWN


@pytest.mark.parametrize("registers", [{11: 5}])
@pytest.mark.usefixtures("init_integration")
async def test_unit_error_shows_the_remote_controller_code(
    hass: HomeAssistant,
) -> None:
    """An error of the air conditioner comes with the code its remote shows."""
    assert hass.states.get(PREFIX + "error").state == "unit_error"
    assert hass.states.get(PREFIX + "error_code").state == "E5"


@pytest.mark.usefixtures("init_integration")
async def test_failed_block_only_takes_its_own_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Sensors read from a block that stops answering go unavailable alone."""
    assert hass.states.get(PREFIX + "outdoor_intake_temperature").state == "12.5"
    mock_connection.for_unit(1).fail_read(60, IllegalDataAddressError())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for key in ("outdoor_intake_temperature", "return_path_temperature"):
        assert hass.states.get(PREFIX + key).state == STATE_UNAVAILABLE
    assert hass.states.get(PREFIX + "error").state == "none"
    assert hass.states.get(PREFIX + "operation_time").state == "1234"


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
    assert hass.states.get(PREFIX + "error_code").state == STATE_UNKNOWN
    assert hass.states.get(PREFIX + "undervoltage_time").state == "3"
    for key in (
        "operation_time",
        "outdoor_intake_temperature",
        "return_path_temperature",
    ):
        assert hass.states.get(PREFIX + key).state == STATE_UNAVAILABLE
    unit.holding[11] = 0
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(PREFIX + "error").state == "none"
    assert hass.states.get(PREFIX + "outdoor_intake_temperature").state == "12.5"
