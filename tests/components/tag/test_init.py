"""Tests for the tag component."""

import logging

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tag import DOMAIN, async_scan_tag
from homeassistant.const import CONF_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import collection
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import TEST_DEVICE_ID, TEST_TAG_ID, TEST_TAG_NAME

from tests.typing import WebSocketGenerator


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage):
    """Storage setup."""

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


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing tags via WS."""
    assert await storage_setup()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert TEST_TAG_ID in result


async def test_ws_update(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing tags via WS."""
    assert await storage_setup()
    await async_scan_tag(hass, "test tag", "some_scanner")

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": TEST_TAG_ID,
            "name": "New name",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    item = resp["result"]

    assert item["id"] == TEST_TAG_ID
    assert item["name"] == "New name"


async def test_tag_scanned(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup,
) -> None:
    """Test scanning tags."""
    assert await storage_setup()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert TEST_TAG_ID in result

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, "new tag", "some_scanner")

    await client.send_json({"id": 7, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 2
    assert TEST_TAG_ID in result
    assert "new tag" in result
    assert result["new tag"]["last_scanned"] == now.isoformat()


def track_changes(coll: collection.ObservableCollection):
    """Create helper to track changes in a collection."""
    changes = []

    async def listener(*args):
        changes.append(args)

    coll.async_add_listener(listener)

    return changes


async def test_tag_id_exists(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test scanning tags."""
    assert await storage_setup()
    changes = track_changes(hass.data[DOMAIN])
    client = await hass_ws_client(hass)

    await client.send_json({"id": 2, "type": f"{DOMAIN}/create", "tag_id": TEST_TAG_ID})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert len(changes) == 0


async def test_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup,
) -> None:
    """Test tag entity."""
    assert await storage_setup()

    await hass_ws_client(hass)

    entity = hass.states.get("tag.test_tag_name")
    assert entity
    assert entity.state == STATE_UNKNOWN

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, TEST_TAG_ID, TEST_DEVICE_ID)

    entity = hass.states.get("tag.test_tag_name")
    assert entity
    assert entity.state == now.isoformat(timespec="milliseconds")
    assert entity.attributes == {
        "tag_id": "test tag id",
        "last_scanned_by_device_id": "device id",
        "friendly_name": "test tag name",
    }


async def test_entity_created_and_removed(
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    storage_setup,
) -> None:
    """Test tag entity created and removed."""
    caplog.at_level(logging.DEBUG)
    assert await storage_setup()

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

    entity = hass.states.get("tag.kitchen_tag")
    assert entity
    assert entity.state == STATE_UNKNOWN

    now = dt_util.utcnow()
    freezer.move_to(now)
    await async_scan_tag(hass, "1234567890", TEST_DEVICE_ID)

    entity = hass.states.get("tag.kitchen_tag")
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

    entity = hass.states.get("tag.kitchen_tag")
    assert not entity
