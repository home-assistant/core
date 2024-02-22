"""Test Subaru device tracker."""
from copy import deepcopy
from unittest.mock import patch

from subarulink.const import LATITUDE, LONGITUDE, TIMESTAMP, VEHICLE_STATUS

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import EXPECTED_STATE_EV_IMPERIAL, VEHICLE_STATUS_EV
from .conftest import MOCK_API_FETCH, MOCK_API_GET_DATA, advance_time_to_next_fetch

DEVICE_ID = "device_tracker.test_vehicle_2"


async def test_device_tracker(hass: HomeAssistant, ev_entry) -> None:
    """Test subaru device tracker entity exists and has correct info."""
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(DEVICE_ID)
    assert entry
    actual = hass.states.get(DEVICE_ID)
    assert (
        actual.attributes.get(ATTR_LONGITUDE) == EXPECTED_STATE_EV_IMPERIAL[LONGITUDE]
    )
    assert actual.attributes.get(ATTR_LATITUDE) == EXPECTED_STATE_EV_IMPERIAL[LATITUDE]


async def test_device_tracker_none_data(hass: HomeAssistant, ev_entry) -> None:
    """Test when location information contains None."""
    bad_status = deepcopy(VEHICLE_STATUS_EV)
    bad_status[VEHICLE_STATUS][LATITUDE] = None
    bad_status[VEHICLE_STATUS][LONGITUDE] = None
    bad_status[VEHICLE_STATUS][TIMESTAMP] = None
    with patch(MOCK_API_FETCH), patch(MOCK_API_GET_DATA, return_value=bad_status):
        advance_time_to_next_fetch(hass)
        await hass.async_block_till_done()

    actual = hass.states.get(DEVICE_ID)
    assert not actual.attributes.get(ATTR_LATITUDE)
    assert not actual.attributes.get(ATTR_LONGITUDE)


async def test_device_tracker_missing_data(hass: HomeAssistant, ev_entry) -> None:
    """Test when location keys are missing from vehicle status."""
    bad_status = deepcopy(VEHICLE_STATUS_EV)
    bad_status[VEHICLE_STATUS].pop(LATITUDE)
    bad_status[VEHICLE_STATUS].pop(LONGITUDE)
    bad_status[VEHICLE_STATUS].pop(TIMESTAMP)
    with patch(MOCK_API_FETCH), patch(MOCK_API_GET_DATA, return_value=bad_status):
        advance_time_to_next_fetch(hass)
        await hass.async_block_till_done()

    actual = hass.states.get(DEVICE_ID)
    assert not actual.attributes.get(ATTR_LATITUDE)
    assert not actual.attributes.get(ATTR_LONGITUDE)
