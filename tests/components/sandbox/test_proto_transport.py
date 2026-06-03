"""T2 transport tests: ProtobufCodec round-trips + the Context security model.

Covers the three guarantees the protobuf wire adds on top of T1:

* a frame survives an encode → decode → re-encode cycle byte-identically (no
  field drops), including fidelity #7's structured voluptuous error data;
* :meth:`SandboxBridge._resolve_context` reuses a known Context and mints a
  fresh one — attributed to the sandbox system user, never carrying a
  sandbox-supplied ``parent_id`` — for an unseen id;
* a sandbox-emitted ``state_changed`` carrying a ``context_id`` lands on main
  with a Context owned by the sandbox system user and no ``parent_id``.
"""

import asyncio

import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.auth import async_get_or_create_sandbox_user
from homeassistant.components.sandbox.bridge import SandboxBridge
from homeassistant.components.sandbox.channel import Frame
from homeassistant.components.sandbox.codec_protobuf import ProtobufCodec
from homeassistant.components.sandbox.messages import (
    make_entity_description,
    struct_to_dict,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant

from ._helpers import make_channel_pair

from tests.common import MockConfigEntry


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    """A loaded light MockConfigEntry registered against ``hass``."""
    entry = MockConfigEntry(
        domain="light", title="Sandboxed Hue", data={"host": "1.2.3.4"}
    )
    entry.add_to_hass(hass)
    return entry


def test_protobuf_codec_round_trip_is_byte_identical() -> None:
    """A full EntityDescription frame re-encodes byte-for-byte after a decode."""
    codec = ProtobufCodec()
    desc = make_entity_description(
        entry_id="entry-1",
        domain="light",
        sandbox_entity_id="light.kitchen",
        unique_id="u-1",
        name="Kitchen",
        has_entity_name=True,
        supported_features=3,
        capabilities={"supported_color_modes": ["onoff", "brightness"]},
        initial_state="on",
        initial_attributes={"brightness": 255, "color_mode": "brightness"},
        device_info={
            "identifiers": [["demo", "dev-1"]],
            "name": "Lamp",
            "sw_version": "1.0",
        },
    )
    frame = Frame.call(7, "sandbox/register_entity", desc)
    wire1 = codec.encode(frame)
    decoded = codec.decode(wire1)
    wire2 = codec.encode(decoded)
    assert wire1 == wire2
    # And no nested field was dropped on the way through.
    assert decoded.payload.info.description.name == "Kitchen"
    assert decoded.payload.info.description.supported_features == 3
    assert decoded.payload.initial.state == "on"
    assert struct_to_dict(decoded.payload.initial.capabilities) == {
        "supported_color_modes": ["onoff", "brightness"]
    }


def test_protobuf_codec_round_trips_response_result() -> None:
    """A success response carries its typed result class through the codec."""
    codec = ProtobufCodec()
    frame = Frame.ok_response(
        9,
        pb.RegisterEntityResult(entity_id="light.kitchen_2"),
        "sandbox/register_entity",
    )
    decoded = codec.decode(codec.encode(frame))
    assert decoded.ok is True
    assert decoded.result.entity_id == "light.kitchen_2"


def test_protobuf_codec_round_trips_invalid_error_data() -> None:
    """Fidelity #7's single-Invalid structured data survives the proto wire."""
    codec = ProtobufCodec()
    frame = Frame.error_response(
        3,
        "expected int",
        "Invalid",
        {"kind": "invalid", "msg": "expected int", "path": ["options", "count"]},
        "sandbox/call_service",
    )
    decoded = codec.decode(codec.encode(frame))
    assert decoded.ok is False
    assert decoded.error == "expected int"
    assert decoded.error_type == "Invalid"
    assert decoded.error_data == {
        "kind": "invalid",
        "msg": "expected int",
        "path": ["options", "count"],
    }


def test_protobuf_codec_round_trips_multiple_invalid_error_data() -> None:
    """A MultipleInvalid keeps its ``multiple`` discriminator + every child."""
    codec = ProtobufCodec()
    error_data = {
        "kind": "multiple",
        "errors": [
            {"kind": "invalid", "msg": "expected int", "path": ["count"]},
            {"kind": "invalid", "msg": "required key", "path": ["name"]},
        ],
    }
    frame = Frame.error_response(
        4, "two errors", "MultipleInvalid", error_data, "sandbox/call_service"
    )
    decoded = codec.decode(codec.encode(frame))
    assert decoded.error_type == "MultipleInvalid"
    assert decoded.error_data == error_data


async def test_resolve_context_caches_known_and_mints_unknown(
    hass: HomeAssistant,
) -> None:
    """A known context_id reuses its Context; an unseen one is minted safely."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    user = await async_get_or_create_sandbox_user(hass, "built-in")

    try:
        known = Context(user_id=user.id, id="known-id")
        bridge._contexts["known-id"] = known
        # A known id returns the exact cached Context.
        assert await bridge._resolve_context("known-id") is known

        # An unseen id mints a fresh Context: the sandbox-supplied id is kept,
        # but it is attributed to the sandbox system user with no parent_id.
        minted = await bridge._resolve_context("fresh-id")
        assert minted.id == "fresh-id"
        assert minted.parent_id is None
        assert minted.user_id == user.id
        # And caching makes a second resolve return the same object.
        assert await bridge._resolve_context("fresh-id") is minted

        # No id at all → a system-user Context, still no parent_id.
        anon = await bridge._resolve_context(None)
        assert anon.parent_id is None
        assert anon.user_id == user.id
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_state_changed_context_attributed_to_sandbox_system_user(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A sandbox state_changed with a context_id lands owned by the system user."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    # Constructing the bridge registers the inbound handlers on main_channel.
    SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()

    desc = make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id="light.lamp",
        unique_id="sandbox-lamp",
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
        initial_state="off",
        initial_attributes={"color_mode": "onoff"},
    )
    try:
        result = await sandbox_channel.call("sandbox/register_entity", desc)
        entity_id = result.entity_id

        changed = pb.StateChanged(
            sandbox_entity_id="light.lamp", state="on", context_id="sandbox-ctx-1"
        )
        changed.attributes.update({"color_mode": "onoff"})
        await sandbox_channel.push("sandbox/state_changed", changed)

        for _ in range(200):
            state = hass.states.get(entity_id)
            if state is not None and state.state == "on":
                break
            await asyncio.sleep(0.01)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    user = await async_get_or_create_sandbox_user(hass, "built-in")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    # The sandbox only sent a context_id; main owns the authoritative Context.
    assert state.context.id == "sandbox-ctx-1"
    assert state.context.user_id == user.id
    assert state.context.parent_id is None
