"""The tests for the Input text component."""
# pylint: disable=protected-access
from unittest.mock import patch

import pytest

from homeassistant.components.input_text import ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_RELOAD
from homeassistant.core import Context, CoreState, State
from homeassistant.exceptions import Unauthorized
from homeassistant.loader import bind_hass
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


@bind_hass
def set_value(hass, entity_id, value):
    """Set input_text to value.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, SERVICE_SET_VALUE, {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value}
        )
    )


async def test_config(hass):
    """Test config."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
        {"test_1": {"min": 50, "max": 50}},
    ]
    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_set_value(hass):
    """Test set_value method."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test_1": {"initial": "test", "min": 3, "max": 10}}}
    )
    entity_id = "input_text.test_1"

    state = hass.states.get(entity_id)
    assert "test" == str(state.state)

    set_value(hass, entity_id, "testing")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "testing" == str(state.state)

    set_value(hass, entity_id, "testing too long")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert "testing" == str(state.state)


async def test_mode(hass):
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
    assert "text" == state.attributes["mode"]

    state = hass.states.get("input_text.test_explicit_text")
    assert state
    assert "text" == state.attributes["mode"]

    state = hass.states.get("input_text.test_explicit_password")
    assert state
    assert "password" == state.attributes["mode"]


async def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (State("input_text.b1", "test"), State("input_text.b2", "testing too long")),
    )

    hass.state = CoreState.starting

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"b1": None, "b2": {"min": 0, "max": 10}}},
    )

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "test"

    state = hass.states.get("input_text.b2")
    assert state
    assert str(state.state) == "unknown"


async def test_initial_state_overrules_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (State("input_text.b1", "testing"), State("input_text.b2", "testing too long")),
    )

    hass.state = CoreState.starting

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


async def test_no_initial_state_and_no_restore_state(hass):
    """Ensure that entity is create without initial and restore feature."""
    hass.state = CoreState.starting

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"b1": {"min": 0, "max": 100}}})

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "unknown"


async def test_input_text_context(hass, hass_admin_user):
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


async def test_config_none(hass):
    """Set up input_text without any config."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"b1": None}})

    state = hass.states.get("input_text.b1")
    assert state
    assert str(state.state) == "unknown"


async def test_reload(hass, hass_admin_user, hass_read_only_user):
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
    assert "test 1" == state_1.state
    assert "test 2" == state_2.state

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_2": {"initial": "test reloaded"},
                "test_3": {"initial": "test 3"},
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

    state_1 = hass.states.get("input_text.test_1")
    state_2 = hass.states.get("input_text.test_2")
    state_3 = hass.states.get("input_text.test_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None
    assert "test reloaded" == state_2.state
    assert "test 3" == state_3.state
