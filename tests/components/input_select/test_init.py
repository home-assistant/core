"""The tests for the Input select component."""
# pylint: disable=protected-access
from unittest.mock import patch

import pytest

from homeassistant.components.input_select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
    SERVICE_SET_OPTIONS,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    SERVICE_RELOAD,
)
from homeassistant.core import Context, State
from homeassistant.exceptions import Unauthorized
from homeassistant.loader import bind_hass
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


@bind_hass
def select_option(hass, entity_id, option):
    """Set value of input_select.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        )
    )


@bind_hass
def select_next(hass, entity_id):
    """Set next value of input_select.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, SERVICE_SELECT_NEXT, {ATTR_ENTITY_ID: entity_id}
        )
    )


@bind_hass
def select_previous(hass, entity_id):
    """Set previous value of input_select.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, SERVICE_SELECT_PREVIOUS, {ATTR_ENTITY_ID: entity_id}
        )
    )


async def test_config(hass):
    """Test config."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
        # {'bad_options': {'options': None}},
        {"bad_initial": {"options": [1, 2], "initial": 3}},
    ]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_select_option(hass):
    """Test select_option methods."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"options": ["some option", "another option"]}}},
    )
    entity_id = "input_select.test_1"

    state = hass.states.get(entity_id)
    assert "some option" == state.state

    select_option(hass, entity_id, "another option")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "another option" == state.state

    select_option(hass, entity_id, "non existing option")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "another option" == state.state


async def test_select_next(hass):
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
    assert "middle option" == state.state

    select_next(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "last option" == state.state

    select_next(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "first option" == state.state


async def test_select_previous(hass):
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
    assert "middle option" == state.state

    select_previous(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "first option" == state.state

    select_previous(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "last option" == state.state


async def test_config_options(hass):
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

    assert "1" == state_1.state
    assert ["1", "2"] == state_1.attributes.get(ATTR_OPTIONS)
    assert ATTR_ICON not in state_1.attributes

    assert "Better Option" == state_2.state
    assert test_2_options == state_2.attributes.get(ATTR_OPTIONS)
    assert "Hello World" == state_2.attributes.get(ATTR_FRIENDLY_NAME)
    assert "mdi:work" == state_2.attributes.get(ATTR_ICON)


async def test_set_options_service(hass):
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
    assert "middle option" == state.state

    data = {ATTR_OPTIONS: ["test1", "test2"], "entity_id": entity_id}
    await hass.services.async_call(DOMAIN, SERVICE_SET_OPTIONS, data)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "test1" == state.state

    select_option(hass, entity_id, "first option")
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert "test1" == state.state

    select_option(hass, entity_id, "test2")
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert "test2" == state.state


async def test_restore_state(hass):
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


async def test_initial_state_overrules_restore_state(hass):
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


async def test_input_select_context(hass, hass_admin_user):
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


async def test_reload(hass, hass_admin_user, hass_read_only_user):
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
    assert "middle option" == state_1.state
    assert "an option" == state_2.state

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
        with patch("homeassistant.config.find_config_file", return_value=""):
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

    state_1 = hass.states.get("input_select.test_1")
    state_2 = hass.states.get("input_select.test_2")
    state_3 = hass.states.get("input_select.test_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None
    assert "reloaded option" == state_2.state
    assert "newer option" == state_3.state
