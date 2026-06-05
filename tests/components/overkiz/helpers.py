"""Shared helpers for Overkiz integration tests."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.converter import converter
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
    name: EventName | str,
    *,
    device_url: str,
    device_states: list[dict[str, Any]] | None = None,
    exec_id: str | None = None,
    new_state: str | None = None,
) -> Event:
    """Create a pyoverkiz event object with a test-friendly interface.

    The raw payload is structured through pyoverkiz's own converter, so the
    result is the same discriminated Event subtype that ``fetch_events`` yields.
    """
    # Call sites pass either an EventName or its string value; normalize both.
    raw: dict[str, Any] = {"name": EventName(name).value, "deviceURL": device_url}

    if device_states is not None:
        raw["deviceStates"] = device_states

    if exec_id is not None:
        raw["execId"] = exec_id

    if new_state is not None:
        # ExecutionStateChangedEvent requires both new_state and old_state; tests
        # only assert on new_state, so default old_state to the same value.
        raw["newState"] = new_state
        raw["oldState"] = new_state

    return converter.structure(raw, Event)


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
