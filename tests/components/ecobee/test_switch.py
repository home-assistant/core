"""The test for the ecobee thermostat switch module."""

import copy
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import patch

import pytest

from homeassistant.components.ecobee.switch import DATE_FORMAT
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP
from .common import setup_platform

VENTILATOR_20MIN_ID = "switch.ecobee_ventilator_20m_timer"
THERMOSTAT_ID = 0


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
        datetime.now() + timedelta(days=1)
    ).strftime(DATE_FORMAT)
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "on"

    data.reset_mock()


async def test_ventilator_20min_when_off(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = (
        datetime.now() - timedelta(days=1)
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
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: VENTILATOR_20MIN_ID},
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
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, False)


DEVICE_ID = "switch.ecobee2_aux_heat_only"


async def test_aux_heat_only_turn_on(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_on:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_on.assert_called_once_with(1, "auxHeatOnly")


async def test_aux_heat_only_turn_off(hass: HomeAssistant) -> None:
    """Test the switch can be turned off."""
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with(1, "auto")
