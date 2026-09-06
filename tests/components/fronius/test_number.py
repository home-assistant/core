"""Tests for the Fronius Modbus setpoint numbers."""

from unittest.mock import patch

from fronius_modbus.testing import build_sunspec_map
from modbus_connection import IllegalDataValueError
from modbus_connection.mock import MockModbusConnection, WriteEvent
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import mock_responses, setup_fronius_integration
from .test_modbus import GEN24_HYBRID_MODULES, assert_state

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

POWER_LIMIT = "number.gen24_storage_ac_power_limit"
CHARGE_LIMIT = "number.gen24_storage_battery_charge_power_limit"


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
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.NUMBER]):
        return await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )


async def test_setpoints_read_from_the_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test the setpoints show what the inverter reports."""
    await _setup(hass, aioclient_mock, mock_fronius_modbus)

    assert_state(hass, POWER_LIMIT, 100.0)
    assert_state(hass, CHARGE_LIMIT, 0.0)
    assert_state(hass, "number.gen24_storage_battery_discharge_power_limit", 0.0)
    assert_state(hass, "number.gen24_storage_battery_minimum_reserve", 20.0)


async def test_setting_a_value_leaves_a_released_limit_released(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a setpoint change doesn't take control back from the inverter.

    Turning a limit off hands control to the next priority source, so a
    change to the setpoint must not quietly re-assert it.
    """
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    controls = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.controls
    assert controls.enabled is False

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: POWER_LIMIT, ATTR_VALUE: 60},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_state(hass, POWER_LIMIT, 60.0)
    assert controls.enabled is False


async def test_setting_a_value_re_enables_an_active_limit(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a change to an active limit is put into effect.

    The device picks up a new setpoint only when the mode is enabled again.
    """
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    coordinator = config_entry.runtime_data.modbus_settings_coordinators[0]
    controls = coordinator.modbus_inverter.controls
    await coordinator.async_write(lambda inverter: inverter.controls, "enabled", True)
    assert controls.enabled is True

    writes: list[WriteEvent] = []
    mock_fronius_modbus.for_unit(1).on_write(writes.append)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: POWER_LIMIT, ATTR_VALUE: 60},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_state(hass, POWER_LIMIT, 60.0)
    assert controls.enabled is True
    # the setpoint, then the enable register that puts it into effect
    assert len(writes) == 2


async def test_battery_setpoint_leaves_the_mode_bits_alone(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a battery setpoint doesn't activate a limit that was off."""
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    storage = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.storage

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CHARGE_LIMIT, ATTR_VALUE: 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_state(hass, CHARGE_LIMIT, 50.0)
    assert storage.charge_limit_enabled is False
    assert storage.discharge_limit_enabled is False


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
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: CHARGE_LIMIT, ATTR_VALUE: 50},
            blocking=True,
        )
