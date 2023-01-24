"""The test for the ecobee thermostat number module."""
from datetime import timedelta
from unittest.mock import patch

from pytest import MonkeyPatch

from homeassistant.components.ecobee.const import DOMAIN as ECOBEE_DOMAIN
from homeassistant.components.number import ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .common import setup_platform

from tests.common import async_fire_time_changed

VENTILATOR_MIN_HOME_ID = "number.ecobee_ventilator_min_time_home"
VENTILATOR_MIN_AWAY_ID = "number.ecobee_ventilator_min_time_away"
THERMOSTAT_ID = 0


async def test_ventilator_min_on_home_attributes(hass):
    """Test the ventilator number on home attributes are correct."""
    await setup_platform(hass, DOMAIN)

    state = hass.states.get(VENTILATOR_MIN_HOME_ID)
    assert state.state == "20"
    assert state.attributes.get("min") == 0
    assert state.attributes.get("max") == 60
    assert state.attributes.get("step") == 5
    assert state.attributes.get("friendly_name") == "ecobee Ventilator min time home"
    assert state.attributes.get("unit_of_measurement") == UnitOfTime.MINUTES


async def test_ventilator_min_on_away_attributes(hass):
    """Test the ventilator number on away attributes are correct."""
    await setup_platform(hass, DOMAIN)

    state = hass.states.get(VENTILATOR_MIN_AWAY_ID)
    assert state.state == "10"
    assert state.attributes.get("min") == 0
    assert state.attributes.get("max") == 60
    assert state.attributes.get("step") == 5
    assert state.attributes.get("friendly_name") == "ecobee Ventilator min time away"
    assert state.attributes.get("unit_of_measurement") == UnitOfTime.MINUTES


async def test_set_min_time_home(hass: HomeAssistant, monkeypatch: MonkeyPatch):
    """Test the number can set min time home."""
    target_value = 40
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_min_on_time_home"
    ) as mock_set_min_home_time:
        await setup_platform(hass, DOMAIN)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: VENTILATOR_MIN_HOME_ID, ATTR_VALUE: target_value},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_min_home_time.assert_called_once_with(THERMOSTAT_ID, target_value)

    data = hass.data[ECOBEE_DOMAIN]

    monkeypatch.setitem(
        data.ecobee.get_thermostat(THERMOSTAT_ID)["settings"],
        "ventilatorMinOnTimeHome",
        target_value,
    )

    with patch("homeassistant.components.ecobee.Ecobee.update"):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get(VENTILATOR_MIN_HOME_ID)
    assert state1.state == str(target_value)


async def test_set_min_time_away(hass: HomeAssistant, monkeypatch: MonkeyPatch) -> None:
    """Test the number can set min time away."""
    target_value = 0
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_min_on_time_away"
    ) as mock_set_min_away_time:
        await setup_platform(hass, DOMAIN)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: VENTILATOR_MIN_AWAY_ID, ATTR_VALUE: target_value},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_min_away_time.assert_called_once_with(THERMOSTAT_ID, target_value)

    data = hass.data[ECOBEE_DOMAIN]

    monkeypatch.setitem(
        data.ecobee.get_thermostat(THERMOSTAT_ID)["settings"],
        "ventilatorMinOnTimeAway",
        target_value,
    )

    with patch("homeassistant.components.ecobee.Ecobee.update"):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get(VENTILATOR_MIN_AWAY_ID)
    assert state1.state == str(target_value)
