"""Shared helpers for Overkiz integration tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
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
    assert mock_client.execute_command.await_count == 1
    args = mock_client.execute_command.await_args.args
    assert args[0] == device_url
    assert args[1].name == command_name
    assert args[1].parameters == (parameters or [])
    assert args[2] == "Home Assistant"


def build_event(
    name: str,
    *,
    device_url: str,
    device_states: list[dict[str, Any]] | None = None,
    exec_id: str | None = None,
    new_state: str | None = None,
) -> Event:
    """Create a pyoverkiz event object with a test-friendly interface."""
    return Event(
        name=name,
        device_url=device_url,
        device_states=device_states,
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
