"""The tests for the persistent notification component."""
import pytest

import homeassistant.components.persistent_notification as pn
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events


@pytest.fixture(autouse=True)
async def setup_integration(hass):
    """Set up persistent notification integration."""
    assert await async_setup_component(hass, pn.DOMAIN, {})


async def test_create(hass):
    """Test creating notification without title or notification id."""
    notifications = hass.data[pn.DOMAIN]
    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 0
    assert len(notifications) == 0

    pn.async_create(hass, "Hello World 2", title="2 beers")

    entity_ids = hass.states.async_entity_ids(pn.DOMAIN)
    assert len(entity_ids) == 1
    assert len(notifications) == 1

    state = hass.states.get(entity_ids[0])
    assert state.state == pn.STATE
    assert state.attributes.get("message") == "Hello World 2"
    assert state.attributes.get("title") == "2 beers"

    notification = notifications.get(entity_ids[0])
    assert notification["status"] == pn.STATUS_UNREAD
    assert notification["message"] == "Hello World 2"
    assert notification["title"] == "2 beers"
    assert notification["created_at"] is not None


async def test_create_notification_id(hass):
    """Ensure overwrites existing notification with same id."""
    notifications = hass.data[pn.DOMAIN]
    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 0
    assert len(notifications) == 0

    pn.async_create(hass, "test", notification_id="Beer 2")

    assert len(hass.states.async_entity_ids()) == 1
    assert len(notifications) == 1

    entity_id = "persistent_notification.beer_2"
    state = hass.states.get(entity_id)
    assert state.attributes.get("message") == "test"

    notification = notifications.get(entity_id)
    assert notification["message"] == "test"
    assert notification["title"] is None

    pn.async_create(hass, "test 2", notification_id="Beer 2")

    # We should have overwritten old one
    assert len(hass.states.async_entity_ids()) == 1
    state = hass.states.get(entity_id)
    assert state.attributes.get("message") == "test 2"

    notification = notifications.get(entity_id)
    assert notification["message"] == "test 2"


async def test_dismiss_notification(hass):
    """Ensure removal of specific notification."""
    notifications = hass.data[pn.DOMAIN]
    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 0
    assert len(notifications) == 0

    pn.async_create(hass, "test", notification_id="Beer 2")

    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 1
    assert len(notifications) == 1
    pn.async_dismiss(hass, notification_id="Beer 2")

    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 0
    assert len(notifications) == 0


async def test_mark_read(hass):
    """Ensure notification is marked as Read."""
    events = async_capture_events(hass, pn.EVENT_PERSISTENT_NOTIFICATIONS_UPDATED)
    notifications = hass.data[pn.DOMAIN]
    assert len(notifications) == 0

    await hass.services.async_call(
        pn.DOMAIN,
        "create",
        {"notification_id": "Beer 2", "message": "test"},
        blocking=True,
    )

    entity_id = "persistent_notification.beer_2"
    assert len(notifications) == 1
    notification = notifications.get(entity_id)
    assert notification["status"] == pn.STATUS_UNREAD
    assert len(events) == 1

    await hass.services.async_call(
        pn.DOMAIN, "mark_read", {"notification_id": "Beer 2"}, blocking=True
    )

    assert len(notifications) == 1
    notification = notifications.get(entity_id)
    assert notification["status"] == pn.STATUS_READ
    assert len(events) == 2

    await hass.services.async_call(
        pn.DOMAIN,
        "dismiss",
        {"notification_id": "Beer 2"},
        blocking=True,
    )
    assert len(notifications) == 0
    assert len(events) == 3


async def test_ws_get_notifications(hass, hass_ws_client):
    """Test websocket endpoint for retrieving persistent notifications."""
    await async_setup_component(hass, pn.DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "persistent_notification/get"})
    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    notifications = msg["result"]
    assert len(notifications) == 0

    # Create
    pn.async_create(hass, "test", notification_id="Beer 2")
    await client.send_json({"id": 6, "type": "persistent_notification/get"})
    msg = await client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    notifications = msg["result"]
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification["notification_id"] == "Beer 2"
    assert notification["message"] == "test"
    assert notification["title"] is None
    assert notification["status"] == pn.STATUS_UNREAD
    assert notification["created_at"] is not None

    # Mark Read
    await hass.services.async_call(
        pn.DOMAIN, "mark_read", {"notification_id": "Beer 2"}
    )
    await client.send_json({"id": 7, "type": "persistent_notification/get"})
    msg = await client.receive_json()
    notifications = msg["result"]
    assert len(notifications) == 1
    assert notifications[0]["status"] == pn.STATUS_READ

    # Dismiss
    pn.async_dismiss(hass, "Beer 2")
    await client.send_json({"id": 8, "type": "persistent_notification/get"})
    msg = await client.receive_json()
    notifications = msg["result"]
    assert len(notifications) == 0
