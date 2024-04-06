"""Tests for the tag component."""

import logging

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.tag import DOMAIN, EVENT_TAG_SCANNED, async_scan_tag
from homeassistant.const import CONF_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_capture_events
from tests.typing import WebSocketGenerator

TEST_TAG_ID = "test tag id"
TEST_TAG_NAME = "test tag name"
TEST_DEVICE_ID = "device id"


@pytest.fixture
def storage_setup_named_tag(
    hass: HomeAssistant,
    hass_storage,
):
    """Storage setup for test case of named tags."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            "id": TEST_TAG_ID,
                            "tag_id": TEST_TAG_ID,
                            CONF_NAME: TEST_TAG_NAME,
                        }
                    ]
                },
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
def storage_setup_unnamed_tag(hass: HomeAssistant, hass_storage):
    """Storage setup for test case of unnamed tags."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": [{"id": TEST_TAG_ID, "tag_id": TEST_TAG_ID}]},
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


async def test_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup_named_tag,
) -> None:
    """Test tag entity."""
    assert await storage_setup_named_tag()

    await hass_ws_client(hass)

    entity = hass.states.get("event.test_tag_name")
    assert entity
    assert entity.state == STATE_UNKNOWN

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, TEST_TAG_ID, TEST_DEVICE_ID)

    entity = hass.states.get("event.test_tag_name")
    assert entity
    assert entity.state == now.isoformat(timespec="milliseconds")
    assert entity.attributes == {
        "event_types": ["tag_scanned"],
        "event_type": "tag_scanned",
        "tag_id": "test tag id",
        "device_id": "device id",
        "friendly_name": "test tag name",
    }


async def test_entity_created_and_removed(
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup_named_tag,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test tag entity created and removed."""
    caplog.at_level(logging.DEBUG)
    assert await storage_setup_named_tag()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/create",
            "tag_id": "1234567890",
            "name": "Kitchen tag",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    item = resp["result"]

    assert item["id"] == "1234567890"
    assert item["name"] == "Kitchen tag"

    entity = hass.states.get("event.kitchen_tag")
    assert entity
    assert entity.state == STATE_UNKNOWN
    assert entity_registry.async_get_entity_id(EVENT_DOMAIN, DOMAIN, "1234567890")

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, "1234567890", TEST_DEVICE_ID)

    entity = hass.states.get("event.kitchen_tag")
    assert entity
    assert entity.state == now.isoformat(timespec="milliseconds")

    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/delete",
            "tag_id": "1234567890",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    entity = hass.states.get("event.kitchen_tag")
    assert not entity
    assert not entity_registry.async_get_entity_id(EVENT_DOMAIN, DOMAIN, "1234567890")
