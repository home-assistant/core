"""The tests for the Input select component."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.input_select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    CONF_INITIAL,
    DOMAIN,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
    SERVICE_SET_OPTIONS,
    STORAGE_VERSION,
    STORAGE_VERSION_MINOR,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockUser, mock_restore_cache
from tests.typing import WebSocketGenerator


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Storage setup."""

    async def _storage(items=None, config=None, minor_version=STORAGE_VERSION_MINOR):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": STORAGE_VERSION,
                "minor_version": minor_version,
                "data": {
                    "items": [
                        {
                            "id": "from_storage",
                            "name": "from storage",
                            "options": ["storage option 1", "storage option 2"],
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "minor_version": minor_version,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_config(hass: HomeAssistant) -> None:
    """Test config."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
        {"bad_initial": {"options": [1, 2], "initial": 3}},
    ]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_select_option(hass: HomeAssistant) -> None:
    """Test select_option methods."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"options": ["some option", "another option"]}}},
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "some option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "another option"},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "another option"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "non existing option"},
            blocking=True,
        )
    state = hass.states.get(entity_id)
    assert state.state == "another option"


async def test_select_next(hass: HomeAssistant) -> None:
    """Test select_next methods."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                }
            }
        },
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "middle option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_NEXT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "last option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_NEXT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "first option"


async def test_select_previous(hass: HomeAssistant) -> None:
    """Test select_previous methods."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                }
            }
        },
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "middle option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_PREVIOUS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "first option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_PREVIOUS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "last option"


async def test_select_first_last(hass: HomeAssistant) -> None:
    """Test select_first and _last methods."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                }
            }
        },
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "middle option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_FIRST,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "first option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_LAST,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "last option"


async def test_config_options(hass: HomeAssistant) -> None:
    """Test configuration options."""
    count_start = len(hass.states.async_entity_ids())

    test_2_options = ["Good Option", "Better Option", "Best Option"]

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {"options": [1, 2]},
                "test_2": {
                    "name": "Hello World",
                    "icon": "mdi:work",
                    "options": test_2_options,
                    "initial": "Better Option",
                },
            }
        },
    )

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_select.test_1")
    state_2 = hass.states.get("input_select.test_2")

    assert state_1 is not None
    assert state_2 is not None

    assert state_1.state == "1"
    assert state_1.attributes.get(ATTR_OPTIONS) == ["1", "2"]
    assert ATTR_ICON not in state_1.attributes

    assert state_2.state == "Better Option"
    assert state_2.attributes.get(ATTR_OPTIONS) == test_2_options
    assert state_2.attributes.get(ATTR_FRIENDLY_NAME) == "Hello World"
    assert state_2.attributes.get(ATTR_ICON) == "mdi:work"


async def test_set_options_service(hass: HomeAssistant) -> None:
    """Test set_options service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                }
            }
        },
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "middle option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OPTIONS,
        {ATTR_OPTIONS: ["first option", "middle option"], ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "middle option"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OPTIONS,
        {ATTR_OPTIONS: ["test1", "test2"], ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "test1"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "first option"},
            blocking=True,
        )
    state = hass.states.get(entity_id)
    assert state.state == "test1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "test2"},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "test2"


async def test_set_options_service_duplicate(hass: HomeAssistant) -> None:
    """Test set_options service with duplicates."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                }
            }
        },
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert state.state == "middle option"
    assert state.attributes[ATTR_OPTIONS] == [
        "first option",
        "middle option",
        "last option",
    ]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_OPTIONS,
            {ATTR_OPTIONS: ["option1", "option1"], ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    state = hass.states.get(entity_id)
    assert state.state == "middle option"
    assert state.attributes[ATTR_OPTIONS] == [
        "first option",
        "middle option",
        "last option",
    ]


async def test_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (
            State("input_select.s1", "last option"),
            State("input_select.s2", "bad option"),
        ),
    )

    options = {"options": ["first option", "middle option", "last option"]}

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"s1": options, "s2": options}})

    state = hass.states.get("input_select.s1")
    assert state
    assert state.state == "last option"

    state = hass.states.get("input_select.s2")
    assert state
    assert state.state == "first option"


async def test_initial_state_overrules_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (
            State("input_select.s1", "last option"),
            State("input_select.s2", "bad option"),
        ),
    )

    options = {
        "options": ["first option", "middle option", "last option"],
        "initial": "middle option",
    }

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"s1": options, "s2": options}})

    state = hass.states.get("input_select.s1")
    assert state
    assert state.state == "middle option"

    state = hass.states.get("input_select.s2")
    assert state
    assert state.state == "middle option"


async def test_input_select_context(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test that input_select context works."""
    assert await async_setup_component(
        hass,
        "input_select",
        {
            "input_select": {
                "s1": {"options": ["first option", "middle option", "last option"]}
            }
        },
    )

    state = hass.states.get("input_select.s1")
    assert state is not None

    await hass.services.async_call(
        "input_select",
        "select_next",
        {"entity_id": state.entity_id},
        True,
        Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("input_select.s1")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


async def test_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                },
                "test_2": {
                    "options": ["an option", "not an option"],
                    "initial": "an option",
                },
            }
        },
    )

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_select.test_1")
    state_2 = hass.states.get("input_select.test_2")
    state_3 = hass.states.get("input_select.test_3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is None
    assert state_1.state == "middle option"
    assert state_2.state == "an option"
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_2": {
                    "options": ["an option", "reloaded option"],
                    "initial": "reloaded option",
                },
                "test_3": {
                    "options": ["new option", "newer option"],
                    "initial": "newer option",
                },
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

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_select.test_1")
    state_2 = hass.states.get("input_select.test_2")
    state_3 = hass.states.get("input_select.test_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None
    assert state_2.state == "an option"
    assert state_3.state == "newer option"
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is not None


async def test_load_from_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "storage option 1"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)
    assert state.attributes.get(ATTR_OPTIONS) == [
        "storage option 1",
        "storage option 2",
    ]


async def test_load_from_storage_duplicate(
    hass: HomeAssistant, storage_setup, caplog: pytest.LogCaptureFixture
) -> None:
    """Test set up from old storage with duplicates."""
    items = [
        {
            "id": "from_storage",
            "name": "from storage",
            "options": ["yaml update 1", "yaml update 2", "yaml update 2"],
        }
    ]
    assert await storage_setup(items, minor_version=1)

    assert (
        "Input select 'from storage' with options "
        "['yaml update 1', 'yaml update 2', 'yaml update 2'] "
        "had duplicated options, the duplicates have been removed"
    ) in caplog.text

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "yaml update 1"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)
    assert state.attributes.get(ATTR_OPTIONS) == ["yaml update 1", "yaml update 2"]


async def test_editable_state_attribute(hass: HomeAssistant, storage_setup) -> None:
    """Test editable attribute."""
    assert await storage_setup(
        config={DOMAIN: {"from_yaml": {"options": ["yaml option", "other option"]}}}
    )

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.state == "storage option 1"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "from storage"
    assert state.attributes.get(ATTR_EDITABLE)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state.state == "yaml option"
    assert not state.attributes.get(ATTR_EDITABLE)


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing via WS."""
    assert await storage_setup(
        config={DOMAIN: {"from_yaml": {"options": ["yaml option"]}}}
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
    """Test updating options updates the state."""

    settings = {
        "name": "from storage",
        "options": ["yaml update 1", "yaml update 2"],
    }
    items = [{"id": "from_storage"} | settings]
    assert await storage_setup(items)

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state.attributes[ATTR_OPTIONS] == ["yaml update 1", "yaml update 2"]
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    updated_settings = settings | {
        "options": ["new option", "newer option"],
        CONF_INITIAL: "newer option",
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
    assert state.attributes[ATTR_OPTIONS] == ["new option", "newer option"]

    # Should fail because the initial state is now invalid
    updated_settings = settings | {
        "options": ["new option", "no newer option"],
        CONF_INITIAL: "newer option",
    }
    await client.send_json(
        {
            "id": 7,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": f"{input_id}",
            **updated_settings,
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]


async def test_update_duplicates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test updating options updates the state."""

    settings = {
        "name": "from storage",
        "options": ["yaml update 1", "yaml update 2"],
    }
    items = [{"id": "from_storage"} | settings]
    assert await storage_setup(items)

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"

    state = hass.states.get(input_entity_id)
    assert state.attributes[ATTR_OPTIONS] == ["yaml update 1", "yaml update 2"]
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    updated_settings = settings | {
        "options": ["new option", "newer option", "newer option"],
        CONF_INITIAL: "newer option",
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
    assert not resp["success"]
    assert resp["error"]["code"] == "home_assistant_error"
    assert resp["error"]["message"] == "Duplicate options are not allowed"

    state = hass.states.get(input_entity_id)
    assert state.attributes[ATTR_OPTIONS] == ["yaml update 1", "yaml update 2"]


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
            "options": ["new option", "even newer option"],
            "initial": "even newer option",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.state == "even newer option"
    assert state.attributes[ATTR_OPTIONS] == ["new option", "even newer option"]


async def test_ws_create_duplicates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test create WS with duplicates."""
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
            "options": ["new option", "even newer option", "even newer option"],
            "initial": "even newer option",
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "home_assistant_error"
    assert resp["error"]["message"] == "Duplicate options are not allowed"

    assert not hass.states.get(input_entity_id)


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
