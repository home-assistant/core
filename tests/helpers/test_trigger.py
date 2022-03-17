"""The tests for the trigger helper."""
from unittest.mock import MagicMock, call, patch

import pytest
import voluptuous as vol

from homeassistant.helpers.trigger import (
    _async_get_trigger_platform,
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
