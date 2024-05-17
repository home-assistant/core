"""Tests for the tag component."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tag import DOMAIN, EVENT_TAG_SCANNED, async_scan_tag
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_capture_events
from tests.typing import WebSocketGenerator

TEST_TAG_ID = "test tag id"
TEST_TAG_NAME = "test tag name"
TEST_DEVICE_ID = "device id"


@pytest.fixture
def storage_setup_named_tag(
    hass,
    hass_storage,
):
    """Storage setup for test case of named tags."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": [{"id": TEST_TAG_ID, CONF_NAME: TEST_TAG_NAME}]},
            }
        else:
            hass_storage[DOMAIN] = items
        config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_named_tag_scanned_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup_named_tag,
) -> None:
    """Test scanning named tag triggering event."""
    assert await storage_setup_named_tag()

    await hass_ws_client(hass)

    events = async_capture_events(hass, EVENT_TAG_SCANNED)

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, TEST_TAG_ID, TEST_DEVICE_ID)

    assert len(events) == 1

    event = events[0]
    event_data = event.data

    assert event_data["name"] == TEST_TAG_NAME
    assert event_data["device_id"] == TEST_DEVICE_ID
    assert event_data["tag_id"] == TEST_TAG_ID


@pytest.fixture
def storage_setup_unnamed_tag(hass, hass_storage):
    """Storage setup for test case of unnamed tags."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": [{"id": TEST_TAG_ID}]},
            }
        else:
            hass_storage[DOMAIN] = items
        config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_unnamed_tag_scanned_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup_unnamed_tag,
) -> None:
    """Test scanning named tag triggering event."""
    assert await storage_setup_unnamed_tag()

    await hass_ws_client(hass)

    events = async_capture_events(hass, EVENT_TAG_SCANNED)

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, TEST_TAG_ID, TEST_DEVICE_ID)

    assert len(events) == 1

    event = events[0]
    event_data = event.data

    assert event_data["name"] is None
    assert event_data["device_id"] == TEST_DEVICE_ID
    assert event_data["tag_id"] == TEST_TAG_ID
