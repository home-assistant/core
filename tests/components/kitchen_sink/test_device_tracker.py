"""The tests for the kitchen_sink device_tracker platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import ATTR_SOURCE_TYPE, SourceType
from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.kitchen_sink.services import (
    ATTR_ACCURACY,
    ATTR_CONNECTED,
    SERVICE_SET_SCANNER_CONNECTED,
    SERVICE_SET_TRACKER_LOCATION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

TRACKER_ENTITY_ID = "device_tracker.demo_tracker"
SCANNER_ENTITY_ID = "device_tracker.demo_scanner"


@pytest.fixture
def device_tracker_only() -> Generator[None]:
    """Enable only the device_tracker platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.DEVICE_TRACKER],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, device_tracker_only: None) -> None:
    """Set up demo component."""
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the expected device_tracker entities are added."""
    states = hass.states.async_all()
    assert set(states) == snapshot


async def test_set_tracker_location(hass: HomeAssistant) -> None:
    """Test the set_tracker_location service updates tracker attributes."""
    state = hass.states.get(TRACKER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SOURCE_TYPE] == SourceType.GPS

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TRACKER_LOCATION,
        {
            ATTR_ENTITY_ID: TRACKER_ENTITY_ID,
            ATTR_LATITUDE: 12.34,
            ATTR_LONGITUDE: 56.78,
            ATTR_ACCURACY: 42,
        },
        blocking=True,
    )

    state = hass.states.get(TRACKER_ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 12.34
    assert state.attributes[ATTR_LONGITUDE] == 56.78
    assert state.attributes[ATTR_GPS_ACCURACY] == 42
    assert state.state == STATE_NOT_HOME


async def test_set_scanner_connected(hass: HomeAssistant) -> None:
    """Test the set_scanner_connected service updates scanner state."""
    state = hass.states.get(SCANNER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes[ATTR_SOURCE_TYPE] == SourceType.ROUTER

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SCANNER_CONNECTED,
        {ATTR_ENTITY_ID: SCANNER_ENTITY_ID, ATTR_CONNECTED: False},
        blocking=True,
    )

    state = hass.states.get(SCANNER_ENTITY_ID)
    assert state.state == STATE_NOT_HOME

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SCANNER_CONNECTED,
        {ATTR_ENTITY_ID: SCANNER_ENTITY_ID, ATTR_CONNECTED: True},
        blocking=True,
    )

    state = hass.states.get(SCANNER_ENTITY_ID)
    assert state.state == STATE_HOME


async def test_set_tracker_location_on_scanner_raises(hass: HomeAssistant) -> None:
    """Calling set_tracker_location on the scanner surfaces an AttributeError.

    The service is registered for the device_tracker domain and dispatches by
    method name, so targeting the scanner (which has no async_set_tracker_location)
    bubbles up the missing-attribute error from the entity.
    """
    with pytest.raises(
        AttributeError,
        match="'DemoScanner' object has no attribute 'async_set_tracker_location'",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TRACKER_LOCATION,
            {
                ATTR_ENTITY_ID: SCANNER_ENTITY_ID,
                ATTR_LATITUDE: 12.34,
                ATTR_LONGITUDE: 56.78,
                ATTR_ACCURACY: 42,
            },
            blocking=True,
        )


async def test_set_scanner_connected_on_tracker_raises(hass: HomeAssistant) -> None:
    """Calling set_scanner_connected on the tracker surfaces an AttributeError."""
    with pytest.raises(
        AttributeError,
        match="'DemoTracker' object has no attribute 'async_set_scanner_connected'",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCANNER_CONNECTED,
            {ATTR_ENTITY_ID: TRACKER_ENTITY_ID, ATTR_CONNECTED: False},
            blocking=True,
        )
