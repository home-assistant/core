"""The tests for frontend storage."""

from typing import Any

import pytest

from homeassistant.components.frontend import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_frontend(hass: HomeAssistant) -> None:
    """Fixture to setup the frontend."""
    await async_setup_component(hass, "frontend", {})


async def test_get_user_data_empty(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_user_data command."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 5, "type": "frontend/get_user_data", "key": "non-existing-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] is None


async def test_get_user_data(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    hass_storage: dict[str, Any],
) -> None:
    """Test get_user_data command."""
    storage_key = f"{DOMAIN}.user_data_{hass_admin_user.id}"
    hass_storage[storage_key] = {
        "key": storage_key,
        "version": 1,
        "data": {"test-key": "test-value", "test-complex": [{"foo": "bar"}]},
    }

    client = await hass_ws_client(hass)

    # Get a simple string key

    await client.send_json(
        {"id": 6, "type": "frontend/get_user_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value"

    # Get a more complex key

    await client.send_json(
        {"id": 7, "type": "frontend/get_user_data", "key": "test-complex"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"][0]["foo"] == "bar"

    # Get all data (no key)

    await client.send_json({"id": 8, "type": "frontend/get_user_data"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"]["test-key"] == "test-value"
    assert res["result"]["value"]["test-complex"][0]["foo"] == "bar"


@pytest.mark.parametrize(
    ("subscriptions", "events"),
    [
        ([], []),
        ([(1, {}, {})], [(1, {"test-key": "test-value"})]),
        ([(1, {"key": "test-key"}, None)], [(1, "test-value")]),
        ([(1, {"key": "other-key"}, None)], []),
    ],
)
async def test_set_user_data_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    subscriptions: list[tuple[int, dict[str, str], Any]],
    events: list[tuple[int, Any]],
) -> None:
    """Test set_user_data command.

    Also test subscribing.
    """
    client = await hass_ws_client(hass)

    for msg_id, key, event_data in subscriptions:
        await client.send_json(
            {
                "id": msg_id,
                "type": "frontend/subscribe_user_data",
            }
            | key
        )

        event = await client.receive_json()
        assert event == {
            "id": msg_id,
            "type": "event",
            "event": {"value": event_data},
        }

        res = await client.receive_json()
        assert res["success"], res

    # test creating

    await client.send_json(
        {"id": 6, "type": "frontend/get_user_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] is None

    await client.send_json(
        {
            "id": 7,
            "type": "frontend/set_user_data",
            "key": "test-key",
            "value": "test-value",
        }
    )

    for msg_id, event_data in events:
        event = await client.receive_json()
        assert event == {"id": msg_id, "type": "event", "event": {"value": event_data}}

    res = await client.receive_json()
    assert res["success"], res

    await client.send_json(
        {"id": 8, "type": "frontend/get_user_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value"


@pytest.mark.parametrize(
    ("subscriptions", "events"),
    [
        (
            [],
            [[], []],
        ),
        (
            [(1, {}, {"test-key": "test-value", "test-complex": "string"})],
            [
                [
                    (
                        1,
                        {
                            "test-complex": "string",
                            "test-key": "test-value",
                            "test-non-existent-key": "test-value-new",
                        },
                    )
                ],
                [
                    (
                        1,
                        {
                            "test-complex": [{"foo": "bar"}],
                            "test-key": "test-value",
                            "test-non-existent-key": "test-value-new",
                        },
                    )
                ],
            ],
        ),
        (
            [(1, {"key": "test-key"}, "test-value")],
            [[], []],
        ),
        (
            [(1, {"key": "test-non-existent-key"}, None)],
            [[(1, "test-value-new")], []],
        ),
        (
            [(1, {"key": "test-complex"}, "string")],
            [[], [(1, [{"foo": "bar"}])]],
        ),
        (
            [(1, {"key": "other-key"}, None)],
            [[], []],
        ),
    ],
)
async def test_set_user_data(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    hass_admin_user: MockUser,
    subscriptions: list[tuple[int, dict[str, str], Any]],
    events: list[list[tuple[int, Any]]],
) -> None:
    """Test set_user_data command with initial data."""
    storage_key = f"{DOMAIN}.user_data_{hass_admin_user.id}"
    hass_storage[storage_key] = {
        "version": 1,
        "data": {"test-key": "test-value", "test-complex": "string"},
    }

    client = await hass_ws_client(hass)

    for msg_id, key, event_data in subscriptions:
        await client.send_json(
            {
                "id": msg_id,
                "type": "frontend/subscribe_user_data",
            }
            | key
        )

        event = await client.receive_json()
        assert event == {
            "id": msg_id,
            "type": "event",
            "event": {"value": event_data},
        }

        res = await client.receive_json()
        assert res["success"], res

    # test creating

    await client.send_json(
        {
            "id": 5,
            "type": "frontend/set_user_data",
            "key": "test-non-existent-key",
            "value": "test-value-new",
        }
    )

    for msg_id, event_data in events[0]:
        event = await client.receive_json()
        assert event == {"id": msg_id, "type": "event", "event": {"value": event_data}}

    res = await client.receive_json()
    assert res["success"], res

    await client.send_json(
        {"id": 6, "type": "frontend/get_user_data", "key": "test-non-existent-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value-new"

    # test updating with complex data

    await client.send_json(
        {
            "id": 7,
            "type": "frontend/set_user_data",
            "key": "test-complex",
            "value": [{"foo": "bar"}],
        }
    )

    for msg_id, event_data in events[1]:
        event = await client.receive_json()
        assert event == {"id": msg_id, "type": "event", "event": {"value": event_data}}

    res = await client.receive_json()
    assert res["success"], res

    await client.send_json(
        {"id": 8, "type": "frontend/get_user_data", "key": "test-complex"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"][0]["foo"] == "bar"

    # ensure other existing key was not modified

    await client.send_json(
        {"id": 9, "type": "frontend/get_user_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value"
