"""The tests for the Template button platform."""
import pytest

from homeassistant import setup
from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context

from tests.common import (
    assert_setup_component,
    async_capture_events,
    async_mock_service,
)

_TEST_BUTTON = "button.template_button"


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_missing_optional_config(hass, calls):
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "test",
                    "button": {
                        "press": {"service": "script.press"},
                        "unique_id": "test",
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN)


async def test_missing_required_keys(hass, calls):
    """Test: missing required fields will fail."""
    with assert_setup_component(0, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {"template": {"button": {}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("button") == []


async def test_all_optional_config(hass, calls):
    """Test: including all optional templates is ok."""
    with assert_setup_component(1, "template"):
        assert await setup.async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "button": {
                        "press": {"service": "test.automation"},
                        "device_class": "restart",
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, "restart")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {CONF_ENTITY_ID: _TEST_BUTTON},
        blocking=True,
    )

    assert len(calls) == 1


async def test_trigger_button(hass):
    """Test trigger based template button."""
    events = async_capture_events(hass, "test_button_event")
    assert await setup.async_setup_component(
        hass,
        "template",
        {
            "template": [
                {"invalid": "config"},
                # Config after invalid should still be set up
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "button": [
                        {
                            "name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "press": {"event": "test_button_event"},
                            "availability": "{{ trigger.event.data.available }}",
                        },
                    ],
                },
            ],
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("button.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire(
        "test_event",
        {"available": False},
        context=context,
    )
    await hass.async_block_till_done()

    state = hass.states.get("button.hello_name")
    assert state.state == STATE_UNAVAILABLE

    context = Context()
    hass.bus.async_fire(
        "test_event",
        {"available": True},
        context=context,
    )
    await hass.async_block_till_done()

    state = hass.states.get("button.hello_name")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {CONF_ENTITY_ID: "button.hello_name"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].event_type == "test_button_event"


def _verify(
    hass,
    expected_value,
    expected_device_class=None,
):
    """Verify button's state."""
    state = hass.states.get(_TEST_BUTTON)
    assert state.state == expected_value
    if expected_device_class:
        assert state.attributes[CONF_DEVICE_CLASS] == expected_device_class
