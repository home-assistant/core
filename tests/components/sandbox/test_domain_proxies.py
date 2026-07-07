"""Per-domain smoke tests for the 28 proxy entities.

Each parametrised case:

1. Wires an in-memory channel pair and a :class:`SandboxBridge`.
2. Pushes a ``sandbox/register_entity`` describing a synthetic entity
   on the domain under test.
3. Pushes a ``sandbox/state_changed`` so the cache reflects a real
   value.
4. Invokes one method on the proxy and asserts the resulting
   ``sandbox/call_service`` RPC carries the expected ``(domain,
   service)`` plus an entity-targeted target list.

The 4 "rich" proxies (light / switch / sensor /
binary_sensor) have dedicated coverage in ``test_bridge.py``; this file
holds the 28 additions plus ``scene`` (which is in ``ALWAYS_MAIN`` but
still ships a proxy for symmetry).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import SandboxBridge
from homeassistant.components.sandbox.channel import Channel
from homeassistant.components.sandbox.messages import (
    decode_json_dict,
    encode_json,
    make_entity_description,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ._helpers import make_channel_pair

from tests.common import MockConfigEntry


async def _wire(
    hass: HomeAssistant,
) -> tuple[SandboxBridge, Channel, Channel]:
    """Return a bridge + main + sandbox in-memory channels."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()
    return bridge, main_channel, sandbox_channel


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    """Mock ConfigEntry the synthetic proxy entities attach to."""
    entry = MockConfigEntry(
        domain="sandbox_synthetic", title="Synthetic", data={}, sandbox="built-in"
    )
    entry.add_to_hass(hass)
    return entry


# Each tuple: (domain, register_payload_extras, state_value,
# state_attributes, proxy_method_name, method_args/kwargs,
# expected_service_name)
_PROXY_CASES: list[tuple[str, dict, str, dict, str, tuple, dict, str]] = [
    (
        "alarm_control_panel",
        {"supported_features": 1},  # ARM_HOME
        "armed_home",
        {},
        "async_alarm_arm_home",
        (),
        {"code": "1234"},
        "alarm_arm_home",
    ),
    (
        "button",
        {},
        "2026-05-23T10:00:00",
        {},
        "async_press",
        (),
        {},
        "press",
    ),
    (
        "calendar",
        {},
        "off",
        {},
        "async_create_event",
        (),
        {"summary": "Lunch"},
        "create_event",
    ),
    (
        "climate",
        {"supported_features": 1},
        "heat",
        {"current_temperature": 21.5, "temperature": 22.0},
        "async_set_temperature",
        (),
        {"temperature": 23.0},
        "set_temperature",
    ),
    (
        "cover",
        {"supported_features": 1},
        "open",
        {"current_position": 90},
        "async_open_cover",
        (),
        {},
        "open_cover",
    ),
    (
        "date",
        {},
        "2026-05-23",
        {},
        "async_set_value",
        (),
        {"value": __import__("datetime").date(2026, 5, 24)},
        "set_value",
    ),
    (
        "datetime",
        {},
        "2026-05-23T10:30:00+00:00",
        {},
        "async_set_value",
        (),
        {
            "value": __import__("datetime").datetime.fromisoformat(
                "2026-05-24T11:00:00+00:00"
            )
        },
        "set_value",
    ),
    (
        "device_tracker",
        {"capabilities": {"source_type": "router"}},
        "home",
        {"source_type": "router"},
        None,
        (),
        {},
        "",
    ),
    (
        "event",
        {"capabilities": {"event_types": ["press", "release"]}},
        "2026-05-23T10:30:00.000+00:00",
        {"event_type": "press"},
        None,
        (),
        {},
        "",
    ),
    (
        "fan",
        {"supported_features": 1},  # SET_SPEED
        "on",
        {"percentage": 50},
        "async_set_percentage",
        (),
        {"percentage": 75},
        "set_percentage",
    ),
    (
        "humidifier",
        {"supported_features": 1},  # MODES
        "on",
        {"humidity": 45},
        "async_set_humidity",
        (),
        {"humidity": 60},
        "set_humidity",
    ),
    (
        "lawn_mower",
        {"supported_features": 1},
        "mowing",
        {},
        "async_start_mowing",
        (),
        {},
        "start_mowing",
    ),
    (
        "lock",
        {"supported_features": 1},
        "locked",
        {},
        "async_unlock",
        (),
        {},
        "unlock",
    ),
    (
        "media_player",
        {"supported_features": 16},  # PLAY
        "playing",
        {"volume_level": 0.5},
        "async_media_pause",
        (),
        {},
        "media_pause",
    ),
    (
        "notify",
        {},
        "2026-05-23T10:30:00",
        {},
        "async_send_message",
        ("hello",),
        {},
        "send_message",
    ),
    (
        "number",
        {"capabilities": {"min": 0, "max": 100, "step": 1}},
        "42",
        {},
        "async_set_native_value",
        (),
        {"value": 73.0},
        "set_value",
    ),
    (
        "remote",
        {"supported_features": 1},
        "on",
        {},
        "async_send_command",
        (["channel_up"],),
        {},
        "send_command",
    ),
    (
        "scene",
        {},
        "2026-05-23T10:30:00",
        {},
        "async_activate",
        (),
        {},
        "turn_on",
    ),
    (
        "select",
        {"capabilities": {"options": ["a", "b", "c"]}},
        "a",
        {},
        "async_select_option",
        (),
        {"option": "b"},
        "select_option",
    ),
    (
        "siren",
        {"supported_features": 1},
        "on",
        {},
        "async_turn_on",
        (),
        {},
        "turn_on",
    ),
    (
        "text",
        {"capabilities": {"min": 0, "max": 100}},
        "hello",
        {},
        "async_set_value",
        ("world",),
        {},
        "set_value",
    ),
    (
        "time",
        {},
        "12:34:56",
        {},
        "async_set_value",
        (),
        {"value": __import__("datetime").time(8, 0)},
        "set_value",
    ),
    (
        "update",
        {"supported_features": 1},  # INSTALL
        "on",
        {"installed_version": "1.0", "latest_version": "1.1"},
        "async_install",
        (),
        {"version": "1.1", "backup": False},
        "install",
    ),
    (
        "vacuum",
        {"supported_features": 1},
        "cleaning",
        {},
        "async_start",
        (),
        {},
        "start",
    ),
    (
        "valve",
        {
            "supported_features": 1,
            "capabilities": {"reports_position": False},
        },
        "open",
        {},
        "async_close_valve",
        (),
        {},
        "close_valve",
    ),
    (
        "water_heater",
        {"supported_features": 1},
        "eco",
        {"current_temperature": 60, "temperature": 65},
        "async_set_operation_mode",
        (),
        {"operation_mode": "performance"},
        "set_operation_mode",
    ),
    (
        "weather",
        {},
        "sunny",
        {"temperature": 20.5},
        None,
        (),
        {},
        "",
    ),
]


@pytest.mark.parametrize(
    (
        "domain",
        "register_extras",
        "state_value",
        "state_attrs",
        "method_name",
        "method_args",
        "method_kwargs",
        "expected_service",
    ),
    [pytest.param(*case, id=case[0]) for case in _PROXY_CASES],
)
async def test_phase13_proxy_smoke(
    hass: HomeAssistant,
    entry: ConfigEntry,
    domain: str,
    register_extras: dict[str, Any],
    state_value: str,
    state_attrs: dict[str, Any],
    method_name: str | None,
    method_args: tuple[Any, ...],
    method_kwargs: dict[str, Any],
    expected_service: str,
) -> None:
    """Each proxy registers, accepts state, and translates a method."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    calls: list[pb.CallService] = []

    async def _on_call_service(payload: pb.CallService) -> Any:
        calls.append(payload)
        return None

    sandbox_channel.register("sandbox/call_service", _on_call_service)

    sandbox_entity_id = f"{domain}.synthetic"
    payload = make_entity_description(
        entry_id=entry.entry_id,
        domain=domain,
        sandbox_entity_id=sandbox_entity_id,
        unique_id=f"sandbox-{domain}",
        supported_features=register_extras.get("supported_features", 0),
        capabilities=register_extras.get("capabilities", {}),
        initial_state=state_value,
        initial_attributes=dict(state_attrs),
    )

    try:
        result = await sandbox_channel.call("sandbox/register_entity", payload)
        # State must round-trip through the cache.
        state_changed = pb.StateChanged(
            sandbox_entity_id=sandbox_entity_id, state=state_value
        )
        state_changed.attributes = encode_json(dict(state_attrs))
        await sandbox_channel.push("sandbox/state_changed", state_changed)
        # Let the state push run.
        for _ in range(20):
            await asyncio.sleep(0)

        proxy = bridge._entities[sandbox_entity_id]
        if method_name is not None:
            await getattr(proxy, method_name)(*method_args, **method_kwargs)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.entity_id.startswith(f"{domain}.")
    state = hass.states.get(result.entity_id)
    assert state is not None, f"state machine missing entry for {domain}"

    if method_name is not None:
        assert len(calls) == 1, f"{domain}: expected one call_service RPC"
        assert calls[0].domain == domain
        assert calls[0].service == expected_service
        assert decode_json_dict(calls[0].target) == {"entity_id": [sandbox_entity_id]}


@pytest.mark.parametrize(
    ("device_class", "pushed_state", "parse"),
    [
        pytest.param(
            "timestamp",
            "2026-05-23T10:30:00+00:00",
            dt_util.parse_datetime,
            id="timestamp",
        ),
        pytest.param("date", "2026-05-23", dt_util.parse_date, id="date"),
    ],
)
async def test_sensor_timestamp_and_date_states_surface(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_class: str,
    pushed_state: str,
    parse: Callable[[str], datetime | date | None],
) -> None:
    """A timestamp/date sensor's pushed ISO string surfaces a working state.

    ``SensorEntity.state`` needs a real ``datetime`` / ``date`` back from
    ``native_value`` — handing it the raw pushed string used to die on
    ``'str' object has no attribute 'tzinfo'``.
    """
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    payload = make_entity_description(
        entry_id=entry.entry_id,
        domain="sensor",
        sandbox_entity_id=f"sensor.synthetic_{device_class}",
        unique_id=f"sandbox-sensor-{device_class}",
        device_class=device_class,
        initial_state=pushed_state,
    )

    try:
        result = await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    state = hass.states.get(result.entity_id)
    assert state is not None
    assert parse(state.state) is not None
    assert parse(state.state) == parse(pushed_state)


async def test_upsert_clears_dropped_device_class(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A re-sent registration without device_class clears the mirrored attr.

    Clearing is symmetric with setting: a field dropped from an upsert must
    not stick from the previous registration.
    """
    bridge, main_channel, sandbox_channel = await _wire(hass)

    def _payload(device_class: str | None) -> pb.EntityDescription:
        return make_entity_description(
            entry_id=entry.entry_id,
            domain="cover",
            sandbox_entity_id="cover.synthetic",
            unique_id="sandbox-cover",
            device_class=device_class,
            supported_features=1,
            initial_state="open",
        )

    try:
        first = await sandbox_channel.call(
            "sandbox/register_entity", _payload("garage")
        )
        proxy = bridge._entities["cover.synthetic"]
        assert proxy._attr_device_class == "garage"

        second = await sandbox_channel.call("sandbox/register_entity", _payload(None))
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert first.entity_id == second.entity_id
    assert proxy._attr_device_class is None
    state = hass.states.get(second.entity_id)
    assert state is not None
    assert "device_class" not in state.attributes
