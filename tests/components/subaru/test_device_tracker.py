"""Test Subaru device tracker."""
from subarulink.const import LATITUDE, LONGITUDE

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import EXPECTED_STATE_EV_IMPERIAL

DEVICE_ID = "device_tracker.test_vehicle_2"


async def test_location(hass: HomeAssistant, ev_entry) -> None:
    """Test subaru location entity exists and has correct info."""
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(DEVICE_ID)
    assert entry
    actual = hass.states.get(DEVICE_ID)
    assert (
        actual.attributes.get(ATTR_LONGITUDE) == EXPECTED_STATE_EV_IMPERIAL[LONGITUDE]
    )
    assert actual.attributes.get(ATTR_LATITUDE) == EXPECTED_STATE_EV_IMPERIAL[LATITUDE]
