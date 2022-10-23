"""The tests for the trigger helper."""
from unittest.mock import ANY, MagicMock, call, patch

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.trigger import (
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


async def test_bad_trigger_platform(hass):
    """Test bad trigger platform."""
    with pytest.raises(vol.Invalid) as ex:
        await async_validate_trigger_config(hass, [{"platform": "not_a_platform"}])
    assert "Invalid platform 'not_a_platform' specified" in str(ex)


async def test_trigger_subtype(hass):
    """Test trigger subtypes."""
    with patch(
        "homeassistant.helpers.trigger.async_get_integration", return_value=MagicMock()
    ) as integration_mock:
        await _async_get_trigger_platform(hass, {"platform": "test.subtype"})
        assert integration_mock.call_args == call(hass, "test")


async def test_trigger_variables(hass):
    """Test trigger variables."""


async def test_if_fires_on_event(hass, calls):
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
