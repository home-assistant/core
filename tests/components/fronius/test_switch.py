"""Tests for the Fronius Modbus control switches."""

from unittest.mock import patch

from fronius_modbus.testing import build_sunspec_map
from modbus_connection import IllegalDataValueError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import mock_responses, setup_fronius_integration
from .test_modbus import GEN24_HYBRID_MODULES, assert_state

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

POWER_LIMITING = "switch.gen24_storage_ac_power_limiting"
CHARGE_LIMITING = "switch.gen24_storage_battery_charge_power_limiting"
DISCHARGE_LIMITING = "switch.gen24_storage_battery_discharge_power_limiting"
GRID_CHARGING = "switch.gen24_storage_battery_grid_charging"


async def _setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    connection: MockModbusConnection,
) -> MockConfigEntry:
    connection.for_unit(1).holding.update(
        build_sunspec_map(
            GEN24_HYBRID_MODULES, storage_wcha_max=12800, storage_min_reserve=20.0
        )
    )
    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SWITCH]):
        return await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )


async def test_switches_read_from_the_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test the switches show what the inverter reports."""
    await _setup(hass, aioclient_mock, mock_fronius_modbus)

    for entity_id in (
        POWER_LIMITING,
        CHARGE_LIMITING,
        DISCHARGE_LIMITING,
        GRID_CHARGING,
    ):
        assert_state(hass, entity_id, STATE_OFF)


@pytest.mark.parametrize(
    ("service", "expected"),
    [(SERVICE_TURN_ON, STATE_ON), (SERVICE_TURN_OFF, STATE_OFF)],
)
async def test_toggling_writes_the_register(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    service: str,
    expected: str,
) -> None:
    """Test toggling a control reaches the device and is read back."""
    await _setup(hass, aioclient_mock, mock_fronius_modbus)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: GRID_CHARGING}, blocking=True
    )
    await hass.async_block_till_done()

    assert_state(hass, GRID_CHARGING, expected)


async def test_limit_switches_keep_each_others_mode_bit(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test the two limit switches share a register without clobbering it.

    Both live in StorCtl_Mod, so writing one has to merge rather than replace.
    """
    await _setup(hass, aioclient_mock, mock_fronius_modbus)

    for entity_id in (CHARGE_LIMITING, DISCHARGE_LIMITING):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        await hass.async_block_till_done()

    assert_state(hass, CHARGE_LIMITING, STATE_ON)
    assert_state(hass, DISCHARGE_LIMITING, STATE_ON)


async def test_turning_a_limit_on_asserts_its_setpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a limit at 100% is an active limit, not a released one.

    Releasing a limit hands control to the next priority source, which may
    impose one of its own. Holding it at 100% is how that gets overridden.
    """
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    controls = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.controls
    assert controls.power_limit == 100.0

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: POWER_LIMITING}, blocking=True
    )
    await hass.async_block_till_done()

    assert_state(hass, POWER_LIMITING, STATE_ON)
    assert controls.power_limit == 100.0


async def test_a_refused_write_raises(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a device rejecting the write surfaces as an error to the user."""
    await _setup(hass, aioclient_mock, mock_fronius_modbus)
    mock_fronius_modbus.for_unit(1).fail_requests(IllegalDataValueError())

    with pytest.raises(HomeAssistantError, match="Could not write"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: POWER_LIMITING},
            blocking=True,
        )
