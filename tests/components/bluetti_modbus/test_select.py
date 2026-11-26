"""Tests for the BLUETTI Modbus selects."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetti_modbus.const import SETTINGS_SCAN_INTERVAL
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

WORKING_MODE_ENTITY = "select.balco_260_working_mode"
WORKING_MODE_ADDRESS = 57020
DISCHARGE_LIMIT_ENTITY = "number.balco_260_discharge_limit"


@pytest.mark.usefixtures("mock_modbus_unit")
@patch("homeassistant.components.bluetti_modbus.PLATFORMS", [Platform.SELECT])
async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All select entities and their states match the snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("option", "raw"),
    [
        pytest.param("custom", 1, id="custom"),
        pytest.param("backup", 4, id="backup"),
    ],
)
async def test_select_writes_the_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    option: str,
    raw: int,
) -> None:
    """Choosing a mode writes its register value, and the state follows at once."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            TargetKey.ENTITY_ID: WORKING_MODE_ENTITY,
            SelectServiceArgument.OPTION: option,
        },
        blocking=True,
    )

    assert mock_modbus_unit.holding[WORKING_MODE_ADDRESS] == raw
    entity = hass.states.get(WORKING_MODE_ENTITY)
    assert entity is not None
    assert entity.state == option


async def test_select_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write the device does not take raises an error and changes nothing."""
    await setup_integration(hass, mock_config_entry)
    mock_modbus_unit.fail_write(WORKING_MODE_ADDRESS, ModbusTimeoutError("timed out"))

    with pytest.raises(HomeAssistantError, match="could not be written"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                TargetKey.ENTITY_ID: WORKING_MODE_ENTITY,
                SelectServiceArgument.OPTION: "backup",
            },
            blocking=True,
        )

    entity = hass.states.get(WORKING_MODE_ENTITY)
    assert entity is not None
    assert entity.state == "self_consumption"


async def test_unknown_working_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A mode the library does not know reads as unknown."""
    await setup_integration(hass, mock_config_entry)

    mock_modbus_unit.holding[WORKING_MODE_ADDRESS] = 3
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(WORKING_MODE_ENTITY)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN


async def test_working_mode_not_served(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A firmware without the working mode register still has its other settings."""
    mock_modbus_unit.fail_read(WORKING_MODE_ADDRESS, IllegalDataAddressError())
    await setup_integration(hass, mock_config_entry)

    entity = hass.states.get(WORKING_MODE_ENTITY)
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE
    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            TargetKey.ENTITY_ID: WORKING_MODE_ENTITY,
            SelectServiceArgument.OPTION: "backup",
        },
        blocking=True,
    )
    assert mock_modbus_unit.holding[WORKING_MODE_ADDRESS] == 2
    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "15"
