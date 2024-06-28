"""The tests for the persistent notification component."""

import homeassistant.components.persistent_notification as pn
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_create(hass: HomeAssistant) -> None:
    """Test creating notification without title or notification id."""
    notifications = pn._async_get_or_create_notifications(hass)
    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 0
    assert len(notifications) == 0

    pn.async_create(hass, "Hello World 2", title="2 beers")
    assert len(notifications) == 1

    notification = notifications[list(notifications)[0]]
    assert notification["message"] == "Hello World 2"
    assert notification["title"] == "2 beers"
    assert notification["created_at"] is not None


async def test_create_notification_id(hass: HomeAssistant) -> None:
    """Ensure overwrites existing notification with same id."""
    notifications = pn._async_get_or_create_notifications(hass)
    assert len(hass.states.async_entity_ids(pn.DOMAIN)) == 0
    assert len(notifications) == 0

    pn.async_create(hass, "test", notification_id="Beer 2")

    assert len(notifications) == 1
    notification = notifications[list(notifications)[0]]

    assert notification["message"] == "test"
    assert notification["title"] is None

    pn.async_create(hass, "test 2", notification_id="Beer 2")

    # We should have overwritten old one
    notification = notifications[list(notifications)[0]]

    assert notification["message"] == "test 2"


async def test_dismiss_notification(hass: HomeAssistant) -> None:
    """Ensure removal of specific notification."""
    notifications = pn._async_get_or_create_notifications(hass)
    assert len(notifications) == 0

    pn.async_create(hass, "test", notification_id="Beer 2")

    assert len(notifications) == 1
    pn.async_dismiss(hass, notification_id="Does Not Exist")

    assert len(notifications) == 1

    pn.async_dismiss(hass, notification_id="Beer 2")

    assert len(notifications) == 0


async def test_dismiss_all_notifications(hass: HomeAssistant) -> None:
    """Ensure removal of all notifications."""
    notifications = pn._async_get_or_create_notifications(hass)
    assert len(notifications) == 0

    pn.async_create(hass, "test", notification_id="Beer 2")
    pn.async_create(hass, "test", notification_id="Beer 3")
    pn.async_create(hass, "test", notification_id="Beer 4")
    pn.async_create(hass, "test", notification_id="Beer 5")

    assert len(notifications) == 4
    pn.async_dismiss_all(hass)

    assert len(notifications) == 0


async def test_ws_get_notifications(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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
    assert notification["created_at"] is not None

    # Dismiss
    pn.async_dismiss(hass, "Beer 2")
    await client.send_json({"id": 8, "type": "persistent_notification/get"})
    msg = await client.receive_json()
    notifications = msg["result"]
    assert len(notifications) == 0


async def test_ws_get_subscribe(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test websocket subscribe endpoint for retrieving persistent notifications."""
    await async_setup_component(hass, pn.DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "persistent_notification/subscribe"})
    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    assert msg["event"]
    event = msg["event"]
    assert event["type"] == "current"
    assert event["notifications"] == {}

    # Create
    pn.async_create(hass, "test", notification_id="Beer 2")

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    assert msg["event"]
    event = msg["event"]
    assert event["type"] == "added"
    notifications = event["notifications"]
    assert len(notifications) == 1
    notification = notifications[list(notifications)[0]]
    assert notification["notification_id"] == "Beer 2"
    assert notification["message"] == "test"
    assert notification["title"] is None
    assert notification["created_at"] is not None

    # Dismiss
    pn.async_dismiss(hass, "Beer 2")
    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    assert msg["event"]
    event = msg["event"]
    assert event["type"] == "removed"


async def test_manual_notification_id_round_trip(hass: HomeAssistant) -> None:
    """Test that a manual notification id can be round tripped."""
    notifications = pn._async_get_or_create_notifications(hass)
    assert len(notifications) == 0

    await hass.services.async_call(
        pn.DOMAIN,
        "create",
        {"notification_id": "synology_diskstation_hub_notification", "message": "test"},
        blocking=True,
    )

    assert len(notifications) == 1

    await hass.services.async_call(
        pn.DOMAIN,
        "dismiss",
        {"notification_id": "synology_diskstation_hub_notification"},
        blocking=True,
    )

    assert len(notifications) == 0


async def test_manual_dismiss_all(hass: HomeAssistant) -> None:
    """Test the dismiss all service."""
    notifications = pn._async_get_or_create_notifications(hass)
    assert len(notifications) == 0

    await hass.services.async_call(
        pn.DOMAIN,
        "create",
        {"notification_id": "Beer 1", "message": "test"},
        blocking=True,
    )

    await hass.services.async_call(
        pn.DOMAIN,
        "create",
        {"notification_id": "Beer 2", "message": "test 2"},
        blocking=True,
    )

    assert len(notifications) == 2

    await hass.services.async_call(
        pn.DOMAIN,
        "dismiss_all",
        None,
        blocking=True,
    )

    assert len(notifications) == 0
