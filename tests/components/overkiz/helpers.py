"""Shared helpers for Overkiz integration tests."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import DataType, EventName, ExecutionState
from pyoverkiz.models import (
    DeviceAvailableEvent,
    DeviceRemovedEvent,
    DeviceStateChangedEvent,
    DeviceUnavailableEvent,
    Event,
    EventState,
    ExecutionStateChangedEvent,
)

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


def device_state_changed_event(
    device_url: str, device_states: list[dict[str, Any]]
) -> DeviceStateChangedEvent:
    """Build a DEVICE_STATE_CHANGED event with the given device states."""
    return DeviceStateChangedEvent(
        name=EventName.DEVICE_STATE_CHANGED,
        device_url=device_url,
        device_states=[
            EventState(
                name=state["name"], type=DataType(state["type"]), value=state["value"]
            )
            for state in device_states
        ],
    )


def device_available_event(device_url: str) -> DeviceAvailableEvent:
    """Build a DEVICE_AVAILABLE event for the given device."""
    return DeviceAvailableEvent(name=EventName.DEVICE_AVAILABLE, device_url=device_url)


def device_unavailable_event(device_url: str) -> DeviceUnavailableEvent:
    """Build a DEVICE_UNAVAILABLE event for the given device."""
    return DeviceUnavailableEvent(
        name=EventName.DEVICE_UNAVAILABLE, device_url=device_url
    )


def device_removed_event(device_url: str) -> DeviceRemovedEvent:
    """Build a DEVICE_REMOVED event for the given device."""
    return DeviceRemovedEvent(name=EventName.DEVICE_REMOVED, device_url=device_url)


def execution_state_changed_event(
    exec_id: str, new_state: ExecutionState, old_state: ExecutionState
) -> ExecutionStateChangedEvent:
    """Build an EXECUTION_STATE_CHANGED event."""
    return ExecutionStateChangedEvent(
        name=EventName.EXECUTION_STATE_CHANGED,
        exec_id=exec_id,
        new_state=new_state,
        old_state=old_state,
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
