"""Test EventType implementation."""

from __future__ import annotations

import orjson

from homeassistant.util.event_type import EventType


def test_compatibility_with_str() -> None:
    """Test EventType. At runtime it should be (almost) fully compatible with str."""

    event = EventType("Hello World")
    assert event == "Hello World"
    assert len(event) == 11
    assert hash(event) == hash("Hello World")
    d: dict[str | EventType, int] = {EventType("key"): 2}
    assert d["key"] == 2


def test_json_dump() -> None:
    """Test EventType json dump with orjson."""

    event = EventType("state_changed")
    assert orjson.dumps({"event_type": event}) == b'{"event_type":"state_changed"}'
