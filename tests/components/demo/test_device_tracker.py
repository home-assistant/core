"""The tests for the demo device tracker platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.demo import DOMAIN
from homeassistant.components.demo.const import SERVICE_RANDOMIZE_DEVICE_TRACKER_DATA
from homeassistant.components.device_tracker import TrackerEntityStateAttribute
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    EntityStateAttribute,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_PAULUS = "device_tracker.paulus"
ENTITY_ANNE_THERESE = "device_tracker.anne_therese"
ENTITY_HOME_BOY = "device_tracker.home_boy"


@pytest.fixture
def device_tracker_only() -> Generator[None]:
    """Enable only the device_tracker platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.DEVICE_TRACKER],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_device_tracker(
    hass: HomeAssistant, device_tracker_only: None
) -> None:
    """Initialize the demo device tracker platform."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test the demo trackers are set up around home."""
    for entity_id in (ENTITY_PAULUS, ENTITY_ANNE_THERESE):
        state = hass.states.get(entity_id)
        assert state.state == STATE_NOT_HOME
        assert (
            abs(state.attributes[EntityStateAttribute.LATITUDE] - hass.config.latitude)
            < 0.01
        )
        assert (
            abs(
                state.attributes[EntityStateAttribute.LONGITUDE] - hass.config.longitude
            )
            < 0.01
        )

    state = hass.states.get(ENTITY_HOME_BOY)
    assert state.state == STATE_HOME
    assert state.attributes[TrackerEntityStateAttribute.GPS_ACCURACY] == 20


async def test_randomize_device_tracker_data(hass: HomeAssistant) -> None:
    """Test the action moves the randomized trackers only."""
    home_boy = hass.states.get(ENTITY_HOME_BOY)

    with patch(
        "homeassistant.components.demo.device_tracker._random_location",
        return_value=(1.0, 2.0, 30),
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_RANDOMIZE_DEVICE_TRACKER_DATA, blocking=True
        )

    for entity_id in (ENTITY_PAULUS, ENTITY_ANNE_THERESE):
        state = hass.states.get(entity_id)
        assert state.attributes[EntityStateAttribute.LATITUDE] == 1.0
        assert state.attributes[EntityStateAttribute.LONGITUDE] == 2.0
        assert state.attributes[TrackerEntityStateAttribute.GPS_ACCURACY] == 30

    assert hass.states.get(ENTITY_HOME_BOY) == home_boy


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test the action no longer moves the trackers after unload."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    await hass.services.async_call(
        DOMAIN, SERVICE_RANDOMIZE_DEVICE_TRACKER_DATA, blocking=True
    )

    assert hass.states.get(ENTITY_PAULUS).state == STATE_UNAVAILABLE
