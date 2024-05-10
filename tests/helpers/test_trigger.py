"""The tests for the trigger helper."""

from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.trigger import (
    DATA_PLUGGABLE_ACTIONS,
    PluggableAction,
    _async_get_trigger_platform,
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_bad_trigger_platform(hass: HomeAssistant) -> None:
    """Test bad trigger platform."""
    with pytest.raises(vol.Invalid) as ex:
        await async_validate_trigger_config(hass, [{"platform": "not_a_platform"}])
    assert "Invalid platform 'not_a_platform' specified" in str(ex)


async def test_trigger_subtype(hass: HomeAssistant) -> None:
    """Test trigger subtypes."""
    with patch(
        "homeassistant.helpers.trigger.async_get_integration",
        return_value=MagicMock(async_get_platform=AsyncMock()),
    ) as integration_mock:
        await _async_get_trigger_platform(hass, {"platform": "test.subtype"})
        assert integration_mock.call_args == call(hass, "test")


async def test_trigger_variables(hass: HomeAssistant) -> None:
    """Test trigger variables."""


async def test_if_fires_on_event(hass: HomeAssistant, calls) -> None:
    """Test the firing of events."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "variables": {
                        "name": "Paulus",
                        "via_event": "{{ trigger.event.event_type }}",
                    },
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"hello": "{{ name }} + {{ via_event }}"},
                },
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["hello"] == "Paulus + test_event"


async def test_if_disabled_trigger_not_firing(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test disabled triggers don't fire."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "platform": "event",
                        "event_type": "enabled_trigger_event",
                    },
                    {
                        "enabled": False,
                        "platform": "event",
                        "event_type": "disabled_trigger_event",
                    },
                ],
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    hass.bus.async_fire("disabled_trigger_event")
    await hass.async_block_till_done()
    assert not calls

    hass.bus.async_fire("enabled_trigger_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_trigger_alias(
    hass: HomeAssistant, calls: list[ServiceCall], caplog: pytest.LogCaptureFixture
) -> None:
    """Test triggers support aliases."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "alias": "My event",
                        "platform": "event",
                        "event_type": "trigger_event",
                    }
                ],
                "action": {
                    "service": "test.automation",
                    "data_template": {"alias": "{{ trigger.alias }}"},
                },
            }
        },
    )

    hass.bus.async_fire("trigger_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["alias"] == "My event"
    assert (
        "Automation trigger 'My event' triggered by event 'trigger_event'"
        in caplog.text
    )


async def test_async_initialize_triggers(
    hass: HomeAssistant, calls: list[ServiceCall], caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_initialize_triggers with different action types."""

    log_cb = MagicMock()

    action_calls = []

    trigger_config = await async_validate_trigger_config(
        hass,
        [
            {
                "platform": "event",
                "event_type": ["trigger_event"],
                "variables": {
                    "name": "Paulus",
                    "via_event": "{{ trigger.event.event_type }}",
                },
            }
        ],
    )

    async def async_action(*args):
        action_calls.append([*args])

    @callback
    def cb_action(*args):
        action_calls.append([*args])

    def non_cb_action(*args):
        action_calls.append([*args])

    for action in (async_action, cb_action, non_cb_action):
        action_calls = []

        unsub = await async_initialize_triggers(
            hass,
            trigger_config,
            action,
            "test",
            "",
            log_cb,
        )
        await hass.async_block_till_done()

        hass.bus.async_fire("trigger_event")
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert len(action_calls) == 1
        assert action_calls[0][0]["name"] == "Paulus"
        assert action_calls[0][0]["via_event"] == "trigger_event"
        log_cb.assert_called_once_with(ANY, "Initialized trigger")

        log_cb.reset_mock()
        unsub()


async def test_pluggable_action(hass: HomeAssistant, calls: list[ServiceCall]):
    """Test normal behavior of pluggable actions."""
    update_1 = MagicMock()
    update_2 = MagicMock()
    action_1 = AsyncMock()
    action_2 = AsyncMock()
    trigger_1 = {"domain": "test", "device": "1"}
    trigger_2 = {"domain": "test", "device": "2"}
    variables_1 = {"source": "test 1"}
    variables_2 = {"source": "test 2"}
    context_1 = Context()
    context_2 = Context()

    plug_1 = PluggableAction(update_1)
    plug_2 = PluggableAction(update_2)

    # Verify plug is inactive without triggers
    remove_plug_1 = plug_1.async_register(hass, trigger_1)
    assert not plug_1
    assert not plug_2

    # Verify plug remain inactive with non matching trigger
    remove_attach_2 = PluggableAction.async_attach_trigger(
        hass, trigger_2, action_2, variables_2
    )
    assert not plug_1
    assert not plug_2
    update_1.assert_not_called()
    update_2.assert_not_called()

    # Verify plug is active, and update when matching trigger attaches
    remove_attach_1 = PluggableAction.async_attach_trigger(
        hass, trigger_1, action_1, variables_1
    )
    assert plug_1
    assert not plug_2
    update_1.assert_called()
    update_1.reset_mock()
    update_2.assert_not_called()

    # Verify a non registered plug is inactive
    remove_plug_1()
    assert not plug_1
    assert not plug_2

    # Verify a plug registered to existing trigger is true
    remove_plug_1 = plug_1.async_register(hass, trigger_1)
    assert plug_1
    assert not plug_2

    remove_plug_2 = plug_2.async_register(hass, trigger_2)
    assert plug_1
    assert plug_2

    # Verify no actions should have been triggered so far
    action_1.assert_not_called()
    action_2.assert_not_called()

    # Verify action is triggered with correct data
    await plug_1.async_run(hass, context_1)
    await plug_2.async_run(hass, context_2)
    action_1.assert_called_with(variables_1, context_1)
    action_2.assert_called_with(variables_2, context_2)

    # Verify plug goes inactive if trigger is removed
    remove_attach_1()
    assert not plug_1

    # Verify registry is cleaned when no plugs nor triggers are attached
    assert hass.data[DATA_PLUGGABLE_ACTIONS]
    remove_plug_1()
    remove_plug_2()
    remove_attach_2()
    assert not hass.data[DATA_PLUGGABLE_ACTIONS]
    assert not plug_2
