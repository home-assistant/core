"""The test for the ecobee thermostat number module."""
from unittest.mock import patch

from homeassistant.components.number import ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTime

from .common import setup_platform

VENTILATOR_MIN_HOME_ID = "number.ecobee_ventilator_min_time_home"
VENTILATOR_MIN_AWAY_ID = "number.ecobee_ventilator_min_time_away"


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


async def test_set_min_time_home(hass):
    """Test the number can set min time home."""
    with patch(
        "pyecobee.Ecobee.set_ventilator_min_on_time_home"
    ) as mock_set_min_home_time:
        await setup_platform(hass, DOMAIN)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: VENTILATOR_MIN_HOME_ID, ATTR_VALUE: 40},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_min_home_time.assert_called_once_with(0, 40)


async def test_set_min_time_away(hass):
    """Test the number can set min time away."""
    with patch(
        "pyecobee.Ecobee.set_ventilator_min_on_time_away"
    ) as mock_set_min_away_time:
        await setup_platform(hass, DOMAIN)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: VENTILATOR_MIN_AWAY_ID, ATTR_VALUE: 0},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_min_away_time.assert_called_once_with(0, 0)
