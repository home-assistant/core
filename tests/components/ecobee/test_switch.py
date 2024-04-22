"""The test for the ecobee thermostat switch module."""

from unittest.mock import patch

from homeassistant.components.switch import DOMAIN, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform

VENTILATOR_20MIN_ID = "switch.ecobee_ventilator_20m_timer"
THERMOSTAT_ID = 0


async def test_ventilator_20min_attributes(hass: HomeAssistant) -> None:
    """Test the ventilator switch on home attributes are correct."""
    await setup_platform(hass, DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"


async def test_ventilator_20min_time_in_past(hass: HomeAssistant) -> None:
    """Test the ventilator switch on home attributes are correct."""
    await setup_platform(hass, DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"


async def test_turn_on_20min_ventilator(hass: HomeAssistant) -> None:
    """Test the switch 20 min timer."""
    target_value = "on"
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_timer"
    ) as mock_set_20min_ventilator:
        await setup_platform(hass, DOMAIN)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, True)

        state = hass.states.get(VENTILATOR_20MIN_ID)
        assert state.state == target_value


async def test_turn_off_20min_ventilator(hass: HomeAssistant) -> None:
    """Test the switch 20 min timer."""
    target_value = "off"
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_timer"
    ) as mock_set_20min_ventilator:
        await setup_platform(hass, DOMAIN)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, False)

        state = hass.states.get(VENTILATOR_20MIN_ID)
        assert state.state == target_value
