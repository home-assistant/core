"""Tests for the Fronius Modbus control selects."""

from unittest.mock import patch

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


@pytest.mark.parametrize(
    ("option", "charge_limit", "discharge_limit", "grid_charging"),
    [
        ("charge", 100.0, -100.0, True),
        ("discharge", -100.0, 100.0, False),
    ],
)
async def test_forcing_the_battery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    option: str,
    charge_limit: float,
    discharge_limit: float,
    grid_charging: bool,
) -> None:
    """Test forcing sets both limits at full power and off resets them."""
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    storage = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.storage

    await _select(hass, option)

    assert_state(hass, FORCED_MODE, option)
    assert storage.charge_limit == charge_limit
    assert storage.discharge_limit == discharge_limit
    assert storage.charge_limit_enabled is True
    assert storage.discharge_limit_enabled is True
    assert storage.grid_charging is grid_charging

    await _select(hass, "off")

    assert_state(hass, FORCED_MODE, "off")
    assert storage.charge_limit == 100.0
    assert storage.discharge_limit == 100.0
    assert storage.charge_limit_enabled is False
    assert storage.discharge_limit_enabled is False
    assert storage.grid_charging is False


@pytest.mark.parametrize(
    ("start", "target"), [("charge", "discharge"), ("discharge", "charge")]
)
async def test_reversing_never_sets_both_rates_negative(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
    start: str,
    target: str,
) -> None:
    """Test going straight from one direction to the other.

    The device refuses a write that leaves both rates negative, so the
    positive rate has to be written before the negative one.
    """
    config_entry = await _setup(hass, aioclient_mock, mock_fronius_modbus)
    storage = config_entry.runtime_data.modbus_settings_coordinators[
        0
    ].modbus_inverter.storage
    await _select(hass, start)
    rates = {
        "charge_limit": storage.charge_limit,
        "discharge_limit": storage.discharge_limit,
    }

    with patch.object(storage, "write", wraps=storage.write) as write:
        await _select(hass, target)

    for call in write.call_args_list:
        field, value = call.args
        if field in rates:
            rates[field] = value
            assert not all(rate < 0 for rate in rates.values())
    assert_state(hass, FORCED_MODE, target)


async def test_a_refused_write_raises(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_fronius_modbus: MockModbusConnection,
) -> None:
    """Test a device rejecting the write surfaces as an error to the user."""
    await _setup(hass, aioclient_mock, mock_fronius_modbus)
    mock_fronius_modbus.for_unit(1).fail_requests(IllegalDataValueError())

    with pytest.raises(HomeAssistantError, match="Could not write"):
        await _select(hass, "charge")
