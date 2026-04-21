"""Tests for Insteon utils."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from pyinsteon.address import Address
from pyinsteon.events import (
    HEARTBEAT_EVENT,
    LEAK_DRY_EVENT,
    LEAK_WET_EVENT,
    LOW_BATTERY_EVENT,
    OFF_EVENT,
    ON_EVENT,
    Event,
)
import pytest

from homeassistant.components.insteon.const import (
    EVENT_CONF_BATTERY,
    EVENT_CONF_BUTTON,
    EVENT_CONF_HEARTBEAT,
    EVENT_CONF_MOISTURE,
)
from homeassistant.components.insteon.utils import add_insteon_events
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import async_capture_events


def test_add_insteon_events_skips_x10_devices(hass: HomeAssistant) -> None:
    """X10 devices should not register Insteon event subscribers."""
    mock_event = MagicMock()
    x10_address = MagicMock()
    x10_address.__str__ = MagicMock(return_value="X10.A.1")

    device = SimpleNamespace(address=x10_address, events={"on": mock_event})

    add_insteon_events(hass, device)

    mock_event.subscribe.assert_not_called()


def test_add_insteon_events_registers_string_keyed_events(hass: HomeAssistant) -> None:
    """Events keyed by name should subscribe the HA bus callback."""
    addr = Address("11.11.11")
    mock_event = MagicMock()
    device = SimpleNamespace(
        address=addr,
        events={"any_key": mock_event},
    )

    add_insteon_events(hass, device)

    mock_event.subscribe.assert_called_once()
    (listener,), kwargs = mock_event.subscribe.call_args
    assert kwargs.get("force_strong_ref") is True
    assert callable(listener)


def test_add_insteon_events_registers_grouped_events(hass: HomeAssistant) -> None:
    """Events nested under an integer group should each be registered."""
    addr = Address("22.22.22")
    ev_a = MagicMock()
    ev_b = MagicMock()
    device = SimpleNamespace(address=addr, events={3: {"a": ev_a, "b": ev_b}})

    add_insteon_events(hass, device)

    ev_a.subscribe.assert_called_once()
    ev_b.subscribe.assert_called_once()


async def test_add_insteon_events_on_event_fires_bus(hass: HomeAssistant) -> None:
    """ON events should fire new and legacy Insteon bus event names."""
    new_events = async_capture_events(hass, "insteon.button_on")
    legacy_events = async_capture_events(hass, "insteon.button_on_event")

    addr = Address("33.33.33")
    on_event = Event(ON_EVENT, addr, group=4, button="button_2")
    device = SimpleNamespace(address=addr, events={"on": on_event})

    add_insteon_events(hass, device)
    on_event.trigger(255)
    await hass.async_block_till_done()

    assert len(new_events) == 1
    assert new_events[0].data[CONF_ADDRESS] == addr.id
    assert new_events[0].data["group"] == 4
    assert new_events[0].data[EVENT_CONF_BUTTON] == "2"

    assert len(legacy_events) == 1
    assert "deprecated" in legacy_events[0].data


async def test_add_insteon_events_off_event_fires_bus(hass: HomeAssistant) -> None:
    """OFF events use the button_ prefix and suffix stripping."""
    captured = async_capture_events(hass, "insteon.button_off")

    addr = Address("44.44.44")
    off_event = Event(OFF_EVENT, addr, group=0, button="xy")
    device = SimpleNamespace(address=addr, events={"off": off_event})

    add_insteon_events(hass, device)
    off_event.trigger(0)
    await hass.async_block_till_done()

    assert len(captured) == 1
    assert EVENT_CONF_BUTTON not in captured[0].data


@pytest.mark.parametrize(
    ("event_name", "kwargs", "expected_key", "expected_value"),
    [
        # Low battery status events
        (
            LOW_BATTERY_EVENT,
            {"low_battery": True},
            EVENT_CONF_BATTERY,
            "low"
        ),
        (
            LOW_BATTERY_EVENT,
            {"low_battery": False},
            EVENT_CONF_BATTERY,"ok"
        ),

        # Heartbeat events
        (
            HEARTBEAT_EVENT,
            {"heartbeat_missed": True},
            EVENT_CONF_HEARTBEAT,
            "missed"
        ),
        (
            HEARTBEAT_EVENT,
            {"heartbeat_missed": False},
            EVENT_CONF_HEARTBEAT,
            "received"
        ),

        # Leak sensor wet/dry events
        (
            LEAK_WET_EVENT,
            {"dry": False},
            EVENT_CONF_MOISTURE,
            "wet"
        ),
        (
            LEAK_DRY_EVENT,
            {"dry": True},
            EVENT_CONF_MOISTURE,
            "dry"
        ),
    ],
)
async def test_add_insteon_events_listener_optional_fields(
    hass: HomeAssistant,
    event_name: str,
    kwargs: dict[str, bool],
    expected_key: str,
    expected_value: str,
) -> None:
    """Optional subscriber kwargs map to Insteon event schema fields."""
    mock_event = MagicMock()
    addr = Address("55.55.55")
    device = SimpleNamespace(address=addr, events={"evt": mock_event})

    add_insteon_events(hass, device)
    (listener,) = mock_event.subscribe.call_args[0]

    captured = async_capture_events(
        hass, f"insteon.{event_name.removesuffix('_event')}")
    listener(event_name, addr.id, 1, **kwargs)
    await hass.async_block_till_done()

    assert len(captured) == 1
    assert captured[0].data[expected_key] == expected_value
