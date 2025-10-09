"""Tests for the Input Weekday component."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.input_weekday import (
    ATTR_WEEKDAY,
    ATTR_WEEKDAYS,
    DOMAIN,
    SERVICE_ADD_WEEKDAY,
    SERVICE_CLEAR,
    SERVICE_REMOVE_WEEKDAY,
    SERVICE_SET_WEEKDAYS,
    SERVICE_TOGGLE_WEEKDAY,
    STORAGE_VERSION,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache
from tests.typing import WebSocketGenerator


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": STORAGE_VERSION,
                "data": {
                    "items": [
                        {
                            "id": "from_storage",
                            "name": "from storage",
                            "weekdays": ["mon", "wed", "fri"],
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": STORAGE_VERSION,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


@pytest.mark.parametrize(
    "invalid_config",
    [
        None,
        {"name with space": None},
        {"bad_weekdays": {"weekdays": ["invalid"]}},
    ],
)
async def test_config(hass: HomeAssistant, invalid_config) -> None:
    """Test config."""
    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: invalid_config})


async def test_set_weekdays(hass: HomeAssistant) -> None:
    """Test set_weekdays service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon", "tue"]}}},
    )
    entity_id = "input_weekday.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "mon,tue"
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "tue"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_WEEKDAYS,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAYS: ["wed", "thu", "fri"]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "wed,thu,fri"
    assert state.attributes[ATTR_WEEKDAYS] == ["wed", "thu", "fri"]


async def test_set_weekdays_removes_duplicates(hass: HomeAssistant) -> None:
    """Test set_weekdays removes duplicate weekdays."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": []}}},
    )
    entity_id = "input_weekday.test_1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_WEEKDAYS,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAYS: ["mon", "tue", "mon", "wed"]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "tue", "wed"]


async def test_add_weekday(hass: HomeAssistant) -> None:
    """Test add_weekday service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon"]}}},
    )
    entity_id = "input_weekday.test_1"

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_WEEKDAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAY: "wed"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed"]

    # Adding duplicate should not add it again
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_WEEKDAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAY: "mon"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed"]


async def test_remove_weekday(hass: HomeAssistant) -> None:
    """Test remove_weekday service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon", "wed", "fri"]}}},
    )
    entity_id = "input_weekday.test_1"

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed", "fri"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_WEEKDAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAY: "wed"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "fri"]

    # Removing non-existent weekday should not error
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_WEEKDAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAY: "wed"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "fri"]


async def test_toggle_weekday(hass: HomeAssistant) -> None:
    """Test toggle_weekday service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon"]}}},
    )
    entity_id = "input_weekday.test_1"

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon"]

    # Toggle off (remove)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE_WEEKDAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAY: "mon"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == []

    # Toggle on (add)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE_WEEKDAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_WEEKDAY: "tue"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["tue"]


async def test_clear(hass: HomeAssistant) -> None:
    """Test clear service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon", "wed", "fri"]}}},
    )
    entity_id = "input_weekday.test_1"

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed", "fri"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == ""
    assert state.attributes[ATTR_WEEKDAYS] == []


async def test_config_with_name(hass: HomeAssistant) -> None:
    """Test configuration with name."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"name": "Test Weekday", "weekdays": ["sat", "sun"]}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state is not None
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test Weekday"
    assert state.attributes[ATTR_WEEKDAYS] == ["sat", "sun"]


async def test_empty_weekdays(hass: HomeAssistant) -> None:
    """Test empty weekdays configuration."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": []}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state is not None
    assert state.state == ""
    assert state.attributes[ATTR_WEEKDAYS] == []


async def test_default_weekdays(hass: HomeAssistant) -> None:
    """Test default weekdays (empty list)."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state is not None
    assert state.state == ""
    assert state.attributes[ATTR_WEEKDAYS] == []


async def test_config_removes_duplicates(hass: HomeAssistant) -> None:
    """Test that configuration removes duplicate weekdays."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon", "tue", "mon", "wed"]}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state is not None
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "tue", "wed"]


async def test_reload(hass: HomeAssistant) -> None:
    """Test reload service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon"]}}},
    )

    state_1 = hass.states.get("input_weekday.test_1")
    state_2 = hass.states.get("input_weekday.test_2")

    assert state_1 is not None
    assert state_2 is None
    assert state_1.attributes[ATTR_WEEKDAYS] == ["mon"]

    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={
            DOMAIN: {
                "test_2": {"weekdays": ["tue", "thu"]},
            }
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
        )
        await hass.async_block_till_done()

    state_1 = hass.states.get("input_weekday.test_1")
    state_2 = hass.states.get("input_weekday.test_2")

    assert state_1 is None
    assert state_2 is not None
    assert state_2.attributes[ATTR_WEEKDAYS] == ["tue", "thu"]


async def test_state_restoration(hass: HomeAssistant) -> None:
    """Test state restoration."""
    mock_restore_cache(
        hass,
        (
            State(
                "input_weekday.test_1",
                "mon,wed,fri",
                {ATTR_WEEKDAYS: ["mon", "wed", "fri"]},
            ),
        ),
    )

    hass.state = "starting"

    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed", "fri"]


async def test_state_restoration_with_initial(hass: HomeAssistant) -> None:
    """Test state restoration with initial value - should prefer initial."""
    mock_restore_cache(
        hass,
        (
            State(
                "input_weekday.test_1",
                "mon,wed,fri",
                {ATTR_WEEKDAYS: ["mon", "wed", "fri"]},
            ),
        ),
    )

    hass.state = "starting"

    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["sat", "sun"]}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state
    assert state.attributes[ATTR_WEEKDAYS] == ["sat", "sun"]


async def test_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test storage."""
    assert await storage_setup()
    state = hass.states.get("input_weekday.from_storage")
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed", "fri"]
    assert state.attributes[ATTR_EDITABLE]


async def test_editable_state_attribute(hass: HomeAssistant) -> None:
    """Test editable attribute."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"weekdays": ["mon"]}}},
    )

    state = hass.states.get("input_weekday.test_1")
    assert state.attributes[ATTR_EDITABLE] is False


async def test_websocket_create(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test create via websocket."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/create",
            "name": "My Weekday",
            "weekdays": ["mon", "fri"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("input_weekday.my_weekday")
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "fri"]


async def test_websocket_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update via websocket."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/create",
            "name": "My Weekday",
            "weekdays": ["mon"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("input_weekday.my_weekday")
    assert state.attributes[ATTR_WEEKDAYS] == ["mon"]

    entity_entry = entity_registry.async_get("input_weekday.my_weekday")

    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": entity_entry.unique_id,
            "weekdays": ["tue", "wed"],
            "name": "Updated Weekday",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("input_weekday.my_weekday")
    assert state.attributes[ATTR_WEEKDAYS] == ["tue", "wed"]
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Updated Weekday"


async def test_websocket_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test delete via websocket."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/create",
            "name": "My Weekday",
            "weekdays": ["mon"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("input_weekday.my_weekday")
    assert state is not None

    entity_entry = entity_registry.async_get("input_weekday.my_weekday")

    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/delete",
            f"{DOMAIN}_id": entity_entry.unique_id,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("input_weekday.my_weekday")
    assert state is None
