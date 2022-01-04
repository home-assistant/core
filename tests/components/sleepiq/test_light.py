"""The tests for SleepIQ light platform."""
from unittest.mock import MagicMock, patch

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.sleepiq import init_integration


async def test_underbed_light(hass: HomeAssistant, requests_mock: MagicMock):
    """Test the SleepIQ under bed light."""
    await init_integration(hass, requests_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("light.sleepnumber_ile_under_bed_light")
    assert state.state == "on"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Under Bed Light"

    entry = entity_registry.async_get("light.sleepnumber_ile_under_bed_light")
    assert entry
    assert entry.unique_id == "-31_light_3"


async def test_turn_on_underbed_light(hass: HomeAssistant, requests_mock: MagicMock):
    """Test turning on the underbed light."""
    await init_integration(hass, requests_mock)

    with patch("sleepyq.Sleepyq.set_light") as mock_client:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.sleepnumber_ile_under_bed_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert mock_client.call_count == 1
        mock_client.assert_called_with(3, 1, "-31")
