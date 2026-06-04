"""Shared helpers for Overkiz integration tests."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
from pyoverkiz.models import Event

from homeassistant.components.overkiz.const import UPDATE_INTERVAL
from homeassistant.core import HomeAssistant

from .conftest import MockOverkizClient

from tests.common import async_fire_time_changed


def assert_command_call(
    mock_client: MockOverkizClient,
    *,
    device_url: str,
    command_name: str,
    parameters: list[Any] | None = None,
) -> None:
    """Assert the latest command sent through the mocked Overkiz client."""
    assert mock_client.execute_action_group.await_count == 1
    kwargs = mock_client.execute_action_group.await_args.kwargs
    assert kwargs["label"] == "Home Assistant"
    actions = kwargs["actions"]
    assert len(actions) == 1
    assert actions[0].device_url == device_url
    assert actions[0].commands[0].name == command_name
    assert actions[0].commands[0].parameters == (parameters or [])


def build_event(
    name: EventName,
    *,
    device_url: str,
    device_states: list[dict[str, Any]] | None = None,
    exec_id: str | None = None,
    new_state: str | None = None,
) -> Event:
    """Create a pyoverkiz event object with a test-friendly interface."""
    # A DeviceStateChangedEvent always carries the changed states; without them
    # the coordinator handler is a silent no-op, so guard against building one.
    if name is EventName.DEVICE_STATE_CHANGED and not device_states:
        raise ValueError("DeviceStateChangedEvent requires device_states")
    return Event(
        name=name,
        device_url=device_url,
        # device_states defaults to None here for caller convenience; Event
        # expects a list, so normalize the omitted case to an empty list.
        device_states=device_states or [],
        exec_id=exec_id,
        new_state=new_state,
    )


async def async_deliver_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    *event_batches: list[Event],
    update_interval: timedelta = UPDATE_INTERVAL,
) -> None:
    """Queue event batches and advance time to trigger a coordinator refresh."""
    mock_client.queue_events(*event_batches)
    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
