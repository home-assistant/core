"""The tests for the notify demo platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components import notify
from homeassistant.components.demo import DOMAIN
import homeassistant.components.demo.notify as demo
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_capture_events


@pytest.fixture
def notify_only() -> Generator[None, None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.NOTIFY],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_notify(hass: HomeAssistant, notify_only: None) -> None:
    """Initialize setup demo Notify entity."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("notify.notifier")
    assert state is not None


@pytest.fixture
def events(hass: HomeAssistant) -> list[Event]:
    """Fixture that catches notify events."""
    return async_capture_events(hass, demo.EVENT_NOTIFY)


@pytest.fixture
def calls():
    """Fixture to calls."""
    return []


@pytest.fixture
def record_calls(calls):
    """Fixture to record calls."""

    @callback
    def record_calls(*args):
        """Record calls."""
        calls.append(args)

    return record_calls


async def test_sending_message(hass: HomeAssistant, events: list[Event]) -> None:
    """Test sending a message."""
    data = {
        "entity_id": "notify.notifier",
        notify.ATTR_MESSAGE: "Test message",
    }
    await hass.services.async_call(notify.DOMAIN, notify.SERVICE_SEND_MESSAGE, data)
    await hass.async_block_till_done()
    last_event = events[-1]
    assert last_event.data == {notify.ATTR_MESSAGE: "Test message"}

    data[notify.ATTR_TITLE] = "My title"
    # Test with Title
    await hass.services.async_call(notify.DOMAIN, notify.SERVICE_SEND_MESSAGE, data)
    await hass.async_block_till_done()
    last_event = events[-1]
    assert last_event.data == {
        notify.ATTR_MESSAGE: "Test message",
        notify.ATTR_TITLE: "My title",
    }


async def test_calling_notify_from_script_loaded_from_yaml(
    hass: HomeAssistant, events: list[Event]
) -> None:
    """Test if we can call a notify from a script."""
    step = {
        "service": "notify.send_message",
        "data": {
            "entity_id": "notify.notifier",
        },
        "data_template": {"message": "Test 123 {{ 2 + 2 }}\n"},
    }
    await async_setup_component(
        hass, "script", {"script": {"test": {"sequence": step}}}
    )
    await hass.services.async_call("script", "test")
    await hass.async_block_till_done()
    assert len(events) == 1
    assert {
        "message": "Test 123 4",
    } == events[0].data
