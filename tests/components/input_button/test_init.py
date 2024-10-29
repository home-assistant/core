"""The tests for the input_test component."""

import logging
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.input_button import DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_NAME,
    SERVICE_RELOAD,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change
from homeassistant.setup import async_setup_component

from tests.common import MockUser, mock_component, mock_restore_cache
from tests.typing import WebSocketGenerator

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": [{"id": "from_storage", "name": "from storage"}]},
            }
        else:
            hass_storage[DOMAIN] = items
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_config(hass: HomeAssistant) -> None:
    """Test config."""
    invalid_configs = [None, 1, {}, {"name with space": None}]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_config_options(hass: HomeAssistant) -> None:
    """Test configuration options."""
    count_start = len(hass.states.async_entity_ids())

    _LOGGER.debug("ENTITIES @ start: %s", hass.states.async_entity_ids())

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": None,
                "test_2": {"name": "Hello World", "icon": "mdi:work"},
            }
        },
    )

    _LOGGER.debug("ENTITIES: %s", hass.states.async_entity_ids())

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_button.test_1")
    state_2 = hass.states.get("input_button.test_2")

    assert state_1 is not None
    assert state_2 is not None

    assert state_1.state == STATE_UNKNOWN
    assert ATTR_ICON not in state_1.attributes
    assert ATTR_FRIENDLY_NAME not in state_1.attributes

    assert state_2.state == STATE_UNKNOWN
    assert state_2.attributes.get(ATTR_FRIENDLY_NAME) == "Hello World"
    assert state_2.attributes.get(ATTR_ICON) == "mdi:work"


async def test_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (State("input_button.b1", "2021-01-01T23:59:59+00:00"),),
    )

    hass.set_state(CoreState.starting)
    mock_component(hass, "recorder")

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"b1": None, "b2": None}})

    state = hass.states.get("input_button.b1")
    assert state
    assert state.state == "2021-01-01T23:59:59+00:00"

    state = hass.states.get("input_button.b2")
    assert state
    assert state.state == STATE_UNKNOWN


async def test_input_button_context(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test that input_button context works."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"update": {}}})

    state = hass.states.get("input_button.update")
    assert state is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: state.entity_id},
        True,
        Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("input_button.update")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


async def test_reload(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hass_admin_user: MockUser
) -> None:
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())

    _LOGGER.debug("ENTITIES @ start: %s", hass.states.async_entity_ids())

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": None,
                "test_2": {"name": "Hello World", "icon": "mdi:work"},
            }
        },
    )

    _LOGGER.debug("ENTITIES: %s", hass.states.async_entity_ids())

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_button.test_1")
    state_2 = hass.states.get("input_button.test_2")
    state_3 = hass.states.get("input_button.test_3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is None

    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_2": {
                    "name": "Hello World reloaded",
                    "icon": "mdi:work_reloaded",
                },
                "test_3": None,
            }
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_button.test_1")
    state_2 = hass.states.get("input_button.test_2")
    state_3 = hass.states.get("input_button.test_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None

    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is not None


async def test_reload_not_changing_state(hass: HomeAssistant, storage_setup) -> None:
    """Test reload not changing state."""
    assert await storage_setup()
    state_changes = []

    def state_changed_listener(entity_id, from_s, to_s):
        state_changes.append(to_s)

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state is not None

    async_track_state_change(hass, [f"{DOMAIN}.from_storage"], state_changed_listener)

    # Pressing button changes state
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: state.entity_id},
        True,
    )
    await hass.async_block_till_done()
    assert len(state_changes) == 1

    # Reloading does not
    with patch(
        "homeassistant.config.load_yaml_config_file", autospec=True, return_value={}
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
        )

    await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state is not None
    assert len(state_changes) == 1


async def test_load_from_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)


async def test_editable_state_attribute(hass: HomeAssistant, storage_setup) -> None:
    """Test editable attribute."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": None}})

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_EDITABLE)


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing via WS."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": None}})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    storage_ent = "from_storage"
    yaml_ent = "from_yaml"
    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert storage_ent in result
    assert yaml_ent not in result
    assert result[storage_ent][ATTR_NAME] == "from storage"


async def test_ws_create_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test creating and updating via WS."""
    assert await storage_setup(config={DOMAIN: {}})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 7, "type": f"{DOMAIN}/create", "name": "new"})
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(f"{DOMAIN}.new")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "new"

    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "new") is not None

    await client.send_json(
        {"id": 8, "type": f"{DOMAIN}/update", f"{DOMAIN}_id": "new", "name": "newer"}
    )
    resp = await client.receive_json()
    assert resp["success"]
    assert resp["result"] == {"id": "new", "name": "newer"}

    state = hass.states.get(f"{DOMAIN}.new")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "newer"

    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "new") is not None


async def test_ws_delete(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{input_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None


async def test_setup_no_config(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test component setup with no config."""
    count_start = len(hass.states.async_entity_ids())
    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.config.load_yaml_config_file", autospec=True, return_value={}
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    assert count_start == len(hass.states.async_entity_ids())
