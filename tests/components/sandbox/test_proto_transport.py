"""T2 transport tests: ProtobufCodec round-trips + the Context security model.

Covers the guarantees the protobuf wire adds on top of T1:

* a frame survives an encode → decode → re-encode cycle byte-identically (no
  field drops), including fidelity #7's structured voluptuous error data;
* :meth:`SandboxBridge._resolve_context` restores a remembered Context
  verbatim (the original ``parent_id`` / ``user_id`` survive the round-trip)
  and mints a **brand-new** main-owned ``Context(user_id=None)`` — with its
  own trusted id, never adopting the sandbox-supplied ULID — for an id main
  never issued;
* the wire carries only a ``context_id`` string — no ``parent_id`` /
  ``user_id`` field exists for the sandbox to forge;
* a sandbox-emitted ``state_changed`` whose ``context_id`` main never issued
  lands on main with a fresh ``user_id=None`` Context and no ``parent_id``.
"""

import asyncio
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import _CONTEXT_TTL, SandboxBridge
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


def test_wire_messages_carry_only_context_id_no_attribution() -> None:
    """The sandbox can only ever send a ``context_id`` string — no forgery.

    There is no ``parent_id`` / ``user_id`` field on any inbound message for
    the sandbox to set, so main never reads sandbox-supplied attribution off
    the wire; it derives the Context entirely on its own side.
    """
    for message in (pb.StateChanged, pb.FireEvent, pb.CallService):
        fields = set(message.DESCRIPTOR.fields_by_name)
        assert "context_id" in fields
        assert "parent_id" not in fields
        assert "user_id" not in fields


async def test_resolve_context_restores_known_and_mints_fresh_unknown(
    hass: HomeAssistant,
) -> None:
    """A remembered id restores verbatim; an unknown id gets a fresh main id."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)

    try:
        # Main remembers a Context it handed down (e.g. the user who pressed a
        # button that triggered a sandboxed automation).
        known = Context(user_id="user-1", parent_id="parent-1")
        bridge._remember_context(known)

        # Echoing that id back restores the *original* Context verbatim.
        restored = bridge._resolve_context(known.id)
        assert restored is known
        assert restored.user_id == "user-1"
        assert restored.parent_id == "parent-1"

        # An id main never issued mints a BRAND-NEW main-owned Context: no
        # fabricated parentage, and crucially its id is main-generated — the
        # untrusted sandbox ULID is NOT adopted (only used as the cache key).
        sandbox_id = "01J0SANDBOXCRAFTEDULID00000"
        minted = bridge._resolve_context(sandbox_id)
        assert minted.user_id is None
        assert minted.parent_id is None
        assert minted.id != sandbox_id
        # Repeated echoes within one operation map to the same stable Context.
        assert bridge._resolve_context(sandbox_id) is minted

        # No id at all → a fresh ``user_id=None`` Context, no parent_id.
        anon = bridge._resolve_context(None)
        assert anon.user_id is None
        assert anon.parent_id is None
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_resolve_context_entry_expires_after_ttl(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An expired entry degrades to a fresh context — safely, never an error."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)

    try:
        known = Context(user_id="user-1", parent_id="parent-1")
        bridge._remember_context(known)
        assert bridge._resolve_context(known.id) is known

        # Past the TTL the entry is pruned; the same id now resolves to a
        # brand-new ``user_id=None`` Context with no parentage — no crash.
        freezer.tick(_CONTEXT_TTL + timedelta(seconds=1))
        fresh = bridge._resolve_context(known.id)
        assert fresh is not known
        assert fresh.user_id is None
        assert fresh.parent_id is None
        # And the expired entry was actually evicted, not just shadowed.
        assert known.id not in bridge._contexts or (
            bridge._contexts[known.id].context is fresh
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_state_changed_unknown_context_gets_fresh_no_user(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A state_changed with an unknown context_id lands with no forged user.

    Main never issued ``sandbox-ctx-1``, so it mints its own trusted Context:
    ``user_id=None``, no ``parent_id``, and an id main generated itself rather
    than the untrusted sandbox-supplied string.
    """
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

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    # Main minted its own Context — no forged attribution, and the untrusted
    # sandbox id was NOT adopted as the Context's identity.
    assert state.context.user_id is None
    assert state.context.parent_id is None
    assert state.context.id != "sandbox-ctx-1"
