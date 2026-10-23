"""Test Subaru device tracker."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from subarulink import SubaruException
from subarulink.const import LATITUDE, LONGITUDE, TIMESTAMP, VEHICLE_STATUS

from homeassistant.components.subaru.const import FETCH_INTERVAL
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import EXPECTED_STATE_EV_IMPERIAL, VEHICLE_STATUS_EV
from .conftest import MOCK_API_FETCH, MOCK_API_GET_DATA, advance_time_to_next_fetch

from tests.common import async_fire_time_changed

DEVICE_ID = "device_tracker.test_vehicle_2"


async def test_device_tracker(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, ev_entry
) -> None:
    """Test subaru device tracker entity exists and has correct info."""
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


@pytest.mark.usefixtures("ev_entry")
async def test_device_tracker_unavailable_on_update_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the device tracker is unavailable while the coordinator update fails."""
    assert hass.states.get(DEVICE_ID).state == STATE_NOT_HOME

    with patch(MOCK_API_FETCH, side_effect=SubaruException("error")):
        freezer.tick(timedelta(seconds=FETCH_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(DEVICE_ID).state == STATE_UNAVAILABLE

    with (
        patch(MOCK_API_FETCH),
        patch(MOCK_API_GET_DATA, return_value=VEHICLE_STATUS_EV),
    ):
        freezer.tick(timedelta(seconds=FETCH_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(DEVICE_ID).state == STATE_NOT_HOME
