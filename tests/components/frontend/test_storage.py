"""The tests for frontend storage."""

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.frontend import DOMAIN
from homeassistant.components.frontend.storage import async_user_store
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
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


async def test_get_system_data_empty(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_system_data command."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 5, "type": "frontend/get_system_data", "key": "non-existing-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] is None


async def test_get_system_data(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test get_system_data command."""
    storage_key = f"{DOMAIN}.system_data"
    hass_storage[storage_key] = {
        "key": storage_key,
        "version": 1,
        "data": {"test-key": "test-value", "test-complex": [{"foo": "bar"}]},
    }

    client = await hass_ws_client(hass)

    # Get a simple string key

    await client.send_json(
        {"id": 6, "type": "frontend/get_system_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value"

    # Get a more complex key

    await client.send_json(
        {"id": 7, "type": "frontend/get_system_data", "key": "test-complex"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"][0]["foo"] == "bar"


@pytest.mark.parametrize(
    ("subscriptions", "events"),
    [
        ([], []),
        ([(1, {"key": "test-key"}, None)], [(1, "test-value")]),
        ([(1, {"key": "other-key"}, None)], []),
    ],
)
async def test_set_system_data_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    subscriptions: list[tuple[int, dict[str, str], Any]],
    events: list[tuple[int, Any]],
) -> None:
    """Test set_system_data command.

    Also test subscribing.
    """
    client = await hass_ws_client(hass)

    for msg_id, key, event_data in subscriptions:
        await client.send_json(
            {
                "id": msg_id,
                "type": "frontend/subscribe_system_data",
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
        {"id": 6, "type": "frontend/get_system_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] is None

    await client.send_json(
        {
            "id": 7,
            "type": "frontend/set_system_data",
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
        {"id": 8, "type": "frontend/get_system_data", "key": "test-key"}
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
async def test_set_system_data(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    subscriptions: list[tuple[int, dict[str, str], Any]],
    events: list[list[tuple[int, Any]]],
) -> None:
    """Test set_system_data command with initial data."""
    storage_key = f"{DOMAIN}.system_data"
    hass_storage[storage_key] = {
        "version": 1,
        "data": {"test-key": "test-value", "test-complex": "string"},
    }

    client = await hass_ws_client(hass)

    for msg_id, key, event_data in subscriptions:
        await client.send_json(
            {
                "id": msg_id,
                "type": "frontend/subscribe_system_data",
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
            "type": "frontend/set_system_data",
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
        {"id": 6, "type": "frontend/get_system_data", "key": "test-non-existent-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value-new"

    # test updating with complex data

    await client.send_json(
        {
            "id": 7,
            "type": "frontend/set_system_data",
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
        {"id": 8, "type": "frontend/get_system_data", "key": "test-complex"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"][0]["foo"] == "bar"

    # ensure other existing key was not modified

    await client.send_json(
        {"id": 9, "type": "frontend/get_system_data", "key": "test-key"}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["value"] == "test-value"


async def test_set_system_data_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test set_system_data requires admin permissions."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {
            "id": 5,
            "type": "frontend/set_system_data",
            "key": "test-key",
            "value": "test-value",
        }
    )

    res = await client.receive_json()
    assert not res["success"], res
    assert res["error"]["code"] == "unauthorized"
    assert res["error"]["message"] == "Unauthorized"


async def test_user_store_concurrent_access(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_storage: dict[str, Any],
) -> None:
    """Test that concurrent access to user store returns loaded data."""
    storage_key = f"{DOMAIN}.user_data_{hass_admin_user.id}"
    hass_storage[storage_key] = {
        "version": 1,
        "data": {"test-key": "test-value"},
    }

    load_count = 0
    original_async_load = Store.async_load

    async def slow_async_load(self: Store) -> Any:
        """Simulate slow loading to trigger race condition."""
        nonlocal load_count
        load_count += 1
        await asyncio.sleep(0)  # Yield to allow other coroutines to run
        return await original_async_load(self)

    with patch.object(Store, "async_load", slow_async_load):
        # Request the same user store concurrently
        results = await asyncio.gather(
            async_user_store(hass, hass_admin_user.id),
            async_user_store(hass, hass_admin_user.id),
            async_user_store(hass, hass_admin_user.id),
        )

    # All results should be the same store instance with loaded data
    assert results[0] is results[1] is results[2]
    assert results[0].data == {"test-key": "test-value"}
    # Store should only be loaded once due to Future synchronization
    assert load_count == 1


async def test_user_store_load_error(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test that load errors are propagated and allow retry."""

    async def failing_async_load(self: Store) -> Any:
        """Simulate a load failure."""
        raise OSError("Storage read error")

    with (
        patch.object(Store, "async_load", failing_async_load),
        pytest.raises(OSError, match="Storage read error"),
    ):
        await async_user_store(hass, hass_admin_user.id)

    # After error, the future should be removed, allowing retry
    # This time without the patch, it should work (empty store)
    store = await async_user_store(hass, hass_admin_user.id)
    assert store.data == {}


async def test_user_store_concurrent_load_error(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test that concurrent callers all receive the same error."""

    async def failing_async_load(self: Store) -> Any:
        """Simulate a slow load failure."""
        await asyncio.sleep(0)  # Yield to allow other coroutines to run
        raise OSError("Storage read error")

    with patch.object(Store, "async_load", failing_async_load):
        results = await asyncio.gather(
            async_user_store(hass, hass_admin_user.id),
            async_user_store(hass, hass_admin_user.id),
            async_user_store(hass, hass_admin_user.id),
            return_exceptions=True,
        )

    # All callers should receive the same OSError
    assert len(results) == 3
    for result in results:
        assert isinstance(result, OSError)
        assert str(result) == "Storage read error"

    # After error, retry should work
    store = await async_user_store(hass, hass_admin_user.id)
    assert store.data == {}
