"""The tests for the Input text component."""
from unittest.mock import patch

import pytest

from homeassistant.components.input_text import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_VALUE,
    CONF_INITIAL,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    DOMAIN,
    MODE_TEXT,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockUser, mock_restore_cache
from tests.typing import WebSocketGenerator

TEST_VAL_MIN = 2
TEST_VAL_MAX = 22


@pytest.fixture
def storage_setup(hass, hass_storage):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            "id": "from_storage",
                            "name": "from storage",
                            "initial": "loaded from storage",
                            ATTR_MAX: TEST_VAL_MAX,
                            ATTR_MIN: TEST_VAL_MIN,
                            ATTR_MODE: MODE_TEXT,
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def async_set_value(hass, entity_id, value):
    """Set input_text to value."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )


async def test_config(hass: HomeAssistant) -> None:
    """Test config."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
        {"test_1": {"min": 50, "max": 50}},
    ]
    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_set_value(hass: HomeAssistant) -> None:
    """Test set_value method."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {"initial": "test", "min": 3, "max": 10},
                "test_2": {},
            }
        },
    )
    entity_id = "input_text.test_1"
    entity_id_2 = "input_text.test_2"
    assert hass.states.get(entity_id).state == "test"
    assert hass.states.get(entity_id_2).state == "unknown"

    for entity in (entity_id, entity_id_2):
        await async_set_value(hass, entity, "testing")
        assert hass.states.get(entity).state == "testing"

    # Too long for entity 1
    await async_set_value(hass, entity, "testing too long")
    assert hass.states.get(entity_id).state == "testing"

    # Set to empty string
    await async_set_value(hass, entity_id_2, "")
    assert hass.states.get(entity_id_2).state == ""


async def test_mode(hass: HomeAssistant) -> None:
    """Test mode settings."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_default_text": {"initial": "test", "min": 3, "max": 10},
                "test_explicit_text": {
                    "initial": "test",
                    "min": 3,
                    "max": 10,
                    "mode": "text",
                },
                "test_explicit_password": {
                    "initial": "test",
                    "min": 3,
                    "max": 10,
                    "mode": "password",
                },
            }
        },
    )

    state = hass.states.get("input_text.test_default_text")
    assert state
    assert state.attributes["mode"] == "text"

    state = hass.states.get("input_text.test_explicit_text")
    assert state
    assert state.attributes["mode"] == "text"

    state = hass.states.get("input_text.test_explicit_password")
    assert state
    assert state.attributes["mode"] == "password"


async def test_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (State("input_text.b1", "test"), State("input_text.b2", "testing too long")),
    )

    hass.set_state(CoreState.starting)

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"b1": None, "b2": {"min": 0, "max": 10}}}
    )

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "test"

    state = hass.states.get("input_text.b2")
    assert state
    assert str(state.state) == "unknown"


async def test_initial_state_overrules_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (State("input_text.b1", "testing"), State("input_text.b2", "testing too long")),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "b1": {"initial": "test", "min": 0, "max": 10},
                "b2": {"initial": "test", "min": 0, "max": 10},
            }
        },
    )

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "test"

    state = hass.states.get("input_text.b2")
    assert state
    assert str(state.state) == "test"


async def test_no_initial_state_and_no_restore_state(hass: HomeAssistant) -> None:
    """Ensure that entity is create without initial and restore feature."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"b1": {"min": 0, "max": 100}}})

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "unknown"


async def test_input_text_context(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test that input_text context works."""
    assert await async_setup_component(
        hass, "input_text", {"input_text": {"t1": {"initial": "bla"}}}
    )

    state = hass.states.get("input_text.t1")
    assert state is not None

    await hass.services.async_call(
        "input_text",
        "set_value",
        {"entity_id": state.entity_id, "value": "new_value"},
        True,
        Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("input_text.t1")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


async def test_config_none(hass: HomeAssistant) -> None:
    """Set up input_text without any config."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"b1": None}})

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "unknown"

    # with empty config we still should have the defaults
    assert state.attributes[ATTR_MODE] == MODE_TEXT
    assert state.attributes[ATTR_MAX] == CONF_MAX_VALUE
    assert state.attributes[ATTR_MIN] == CONF_MIN_VALUE


async def test_reload(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_read_only_user: MockUser
) -> None:
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())

    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"initial": "test 1"}, "test_2": {"initial": "test 2"}}},
    )

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_text.test_1")
    state_2 = hass.states.get("input_text.test_2")
    state_3 = hass.states.get("input_text.test_3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is None
    assert state_1.state == "test 1"
    assert state_2.state == "test 2"
    assert state_1.attributes[ATTR_MIN] == 0
    assert state_2.attributes[ATTR_MAX] == 100

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_2": {"initial": "test reloaded", ATTR_MIN: 12},
                "test_3": {"initial": "test 3", ATTR_MAX: 21},
            }
        },
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_text.test_1")
    state_2 = hass.states.get("input_text.test_2")
    state_3 = hass.states.get("input_text.test_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None
    assert state_2.attributes[ATTR_MIN] == 12
    assert state_3.attributes[ATTR_MAX] == 21


async def test_load_from_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "loaded from storage"
    assert state.attributes.get(ATTR_EDITABLE)
    assert state.attributes[ATTR_MAX] == TEST_VAL_MAX
    assert state.attributes[ATTR_MIN] == TEST_VAL_MIN


async def test_editable_state_attribute(hass: HomeAssistant, storage_setup) -> None:
    """Test editable attribute."""
    assert await storage_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    "initial": "yaml initial value",
                    ATTR_MODE: MODE_TEXT,
                    ATTR_MAX: 33,
                    ATTR_MIN: 3,
                    ATTR_NAME: "yaml friendly name",
                }
            }
        }
    )

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "loaded from storage"
    assert state.attributes.get(ATTR_EDITABLE)
    assert state.attributes[ATTR_MAX] == TEST_VAL_MAX
    assert state.attributes[ATTR_MIN] == TEST_VAL_MIN

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state.state == "yaml initial value"
    assert not state.attributes[ATTR_EDITABLE]
    assert state.attributes[ATTR_MAX] == 33
    assert state.attributes[ATTR_MIN] == 3


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing via WS."""
    assert await storage_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    "initial": "yaml initial value",
                    ATTR_MODE: MODE_TEXT,
                    ATTR_MAX: 33,
                    ATTR_MIN: 3,
                    ATTR_NAME: "yaml friendly name",
                }
            }
        }
    )

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


async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test updating min/max updates the state."""

    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"
    assert state.attributes[ATTR_MODE] == MODE_TEXT
    assert state.state == "loaded from storage"
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    updated_settings = {
        ATTR_NAME: "even newer name",
        CONF_INITIAL: "newer option",
        ATTR_MAX: TEST_VAL_MAX,
        ATTR_MIN: 6,
        ATTR_MODE: "password",
    }
    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": f"{input_id}",
            **updated_settings,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    assert resp["result"] == {"id": "from_storage"} | updated_settings

    state = hass.states.get(input_entity_id)
    assert state.state == "loaded from storage"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "even newer name"
    assert state.attributes[ATTR_MODE] == "password"
    assert state.attributes[ATTR_MIN] == 6
    assert state.attributes[ATTR_MAX] == TEST_VAL_MAX


async def test_ws_create(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test create WS."""
    assert await storage_setup(items=[])

    input_id = "new_input"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/create",
            "name": "New Input",
            "initial": "even newer option",
            ATTR_MAX: 44,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.state == "even newer option"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "New Input"
    assert state.attributes[ATTR_EDITABLE]
    assert state.attributes[ATTR_MAX] == 44
    assert state.attributes[ATTR_MIN] == 0


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
        await hass.async_block_till_done()

    assert count_start == len(hass.states.async_entity_ids())
