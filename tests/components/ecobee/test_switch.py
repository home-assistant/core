"""The test for the ecobee thermostat switch module."""

import copy
from datetime import timedelta
from unittest import mock
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant.common import mock_restore_cache_with_extra_data

from homeassistant.components.ecobee.switch import DATE_FORMAT
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from . import GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP
from .common import setup_platform

VENTILATOR_20MIN_ID = "switch.ecobee_ventilator_20m_timer"
THERMOSTAT_ID = 0
THERMOSTAT_TIMEZONE = ZoneInfo(
    GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP["location"]["timeZone"]
)


@pytest.fixture(name="data")
def data_fixture():
    """Set up data mock."""
    data = mock.Mock()
    data.return_value = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    return data


async def test_ventilator_20min_attributes(hass: HomeAssistant) -> None:
    """Test the ventilator switch on home attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"


async def test_ventilator_20min_when_on(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = (
        dt_util.now(THERMOSTAT_TIMEZONE) + timedelta(days=1)
    ).strftime(DATE_FORMAT)
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "on"

    data.reset_mock()


async def test_ventilator_20min_when_off(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = (
        dt_util.now(THERMOSTAT_TIMEZONE) - timedelta(days=1)
    ).strftime(DATE_FORMAT)
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"

    data.reset_mock()


async def test_ventilator_20min_when_empty(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = ""
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"

    data.reset_mock()


async def test_turn_on_20min_ventilator(hass: HomeAssistant) -> None:
    """Test the switch 20 min timer (On)."""

    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_timer"
    ) as mock_set_20min_ventilator:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, True)


async def test_turn_off_20min_ventilator(hass: HomeAssistant) -> None:
    """Test the switch 20 min timer (off)."""

    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_timer"
    ) as mock_set_20min_ventilator:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, False)


DEVICE_ID = "switch.ecobee2_auxiliary_heat_only"


async def test_aux_heat_only_turn_on(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_on:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_on.assert_called_once_with(1, "auxHeatOnly")


async def test_aux_heat_only_turn_on_when_on(hass: HomeAssistant) -> None:
    """Test turning on the switch again doesn't overwrite the saved HVAC mode."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(DEVICE_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_on:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_on.assert_not_called()


async def test_aux_heat_only_turn_off(hass: HomeAssistant) -> None:
    """Test turning off the switch without a saved mode does not change HVAC mode."""
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_off.assert_not_called()


async def test_aux_heat_only_turn_off_after_restart(hass: HomeAssistant) -> None:
    """Test the switch restores the prior mode after a Home Assistant restart."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(DEVICE_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with(1, "heat")


async def test_aux_heat_only_turn_off_when_off(hass: HomeAssistant) -> None:
    """Test turning off an already-off switch does not change HVAC mode."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(DEVICE_ID, "off"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_off.assert_not_called()


async def test_aux_heat_only_turn_off_with_invalid_restore_mode(
    hass: HomeAssistant,
) -> None:
    """Test turning off with an unknown HVAC mode is a no-op."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(DEVICE_ID, "on"),
                {"hvac_mode_before_aux_heat": "invalid"},
            )
        ],
    )
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_off.assert_not_called()


async def test_aux_heat_only_clears_previous_mode_when_changed_remotely(
    hass: HomeAssistant,
) -> None:
    """Test an external HVAC mode change clears the saved auxiliary heat mode."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    get_thermostat = mock.Mock(return_value=thermostat)
    with (
        patch("pyecobee.Ecobee.get_thermostat", get_thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_set_hvac_mode,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        get_thermostat.reset_mock()
        get_thermostat.return_value["settings"]["hvacMode"] = "heat"

        hass.states.async_set("sensor.force_update", "1")
        await hass.async_block_till_done()
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )

        mock_set_hvac_mode.assert_not_called()
