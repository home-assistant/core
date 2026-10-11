"""Tests for the Fronius Modbus control selects."""

from unittest.mock import patch

from fronius_modbus import ForcedMode
from fronius_modbus.testing import build_sunspec_map
from modbus_connection import IllegalDataValueError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import mock_responses, setup_fronius_integration
from .test_modbus import GEN24_HYBRID_MODULES, assert_state

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

FORCED_MODE = "select.gen24_storage_battery_forced_mode"


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
    with patch("homeassistant.components.fronius.PLATFORMS", [Platform.SELECT]):
        return await setup_fronius_integration(
            hass, is_logger=False, unique_id="12345678"
        )


async def _select(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: FORCED_MODE, ATTR_OPTION: option},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_forced_mode_read_from_the_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test the mode shows what the inverter reports."""
    await _setup(hass, aioclient_mock, mock_fronius_modbus)

    assert_state(hass, FORCED_MODE, "off")


@pytest.mark.parametrize("mode", [ForcedMode.CHARGE, ForcedMode.DISCHARGE])
async def test_forcing_the_battery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    mode: ForcedMode,
) -> None:
    """Test forcing reaches the device and off releases it again."""
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    storage = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.storage

    await _select(hass, mode)

    assert_state(hass, FORCED_MODE, mode)
    assert storage.forced_mode is mode

    await _select(hass, "off")

    assert_state(hass, FORCED_MODE, "off")
    assert storage.charge_limit_enabled is False
    assert storage.discharge_limit_enabled is False


async def test_a_refused_write_raises_and_refreshes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a device rejecting a write surfaces and shows what did go through.

    The mode is a sequence of writes, so ones before the refused write may
    have reached the device.
    """
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    storage = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.storage

    async def force_then_refuse(mode: ForcedMode) -> None:
        await storage.set_limits(discharge=-100)
        raise IllegalDataValueError

    with (
        patch.object(storage, "set_forced_mode", side_effect=force_then_refuse),
        pytest.raises(HomeAssistantError, match="Could not write"),
    ):
        await _select(hass, "charge")

    assert_state(hass, FORCED_MODE, "charge")
