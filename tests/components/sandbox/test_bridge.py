"""Tests for the :class:`SandboxBridge` — main-side entity bridge."""

import asyncio
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import _CONTEXT_CACHE_MAX, SandboxBridge
from homeassistant.components.sandbox.channel import Channel, ChannelRemoteError
from homeassistant.components.sandbox.description import SandboxEntityDescription
from homeassistant.components.sandbox.messages import (
    decode_json_dict,
    encode_json,
    make_entity_description,
)
from homeassistant.components.sandbox.service_forwarder import translate_remote_error
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ._helpers import make_channel_pair

from tests.common import MockConfigEntry


async def _wire(
    hass: HomeAssistant,
) -> tuple[SandboxBridge, Channel, Channel]:
    """Build a bridge connected to an in-memory channel-pair sandbox stub."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()
    return bridge, main_channel, sandbox_channel


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """Suppress strings.json checks for the service-mirror mock domains."""
    return ["mirror_demo", "mirror_local"]


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    """A loaded MockConfigEntry routed to the ``built-in`` sandbox group."""
    entry = MockConfigEntry(
        domain="light",
        title="Sandboxed Hue",
        data={"host": "1.2.3.4"},
        sandbox="built-in",
    )
    entry.add_to_hass(hass)
    return entry


async def test_register_entity_creates_proxy_and_returns_entity_id(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A ``register_entity`` push creates a live proxy on the right domain."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    payload = make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id="light.kitchen",
        unique_id="sandbox-kitchen",
        name="Kitchen",
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
        initial_state=STATE_ON,
        # Light requires color_mode when ON, so feed it through the
        # initial cache to keep state_attributes from raising.
        initial_attributes={"color_mode": "onoff"},
    )

    try:
        result = await sandbox_channel.call("sandbox/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.entity_id.startswith("light.")
    state = hass.states.get(result.entity_id)
    assert state is not None
    assert state.state == STATE_ON
    # The bridge tracks the proxy by its sandbox-side entity_id.
    assert "light.kitchen" in bridge._entities


async def test_register_entity_prefixes_unique_id_with_source_domain(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Two integrations reusing unique_id ``"1"`` land without colliding.

    All proxies share ``platform_name="sandbox"``, so the registry key
    ``("light", "sandbox", unique_id)`` would clash if the unique_id
    weren't namespaced with the source integration domain.
    """
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    entry_a = MockConfigEntry(domain="demo_a", title="A", sandbox="built-in")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="demo_b", title="B", sandbox="built-in")
    entry_b.add_to_hass(hass)

    def _payload(entry_id: str, sandbox_entity_id: str) -> pb.EntityDescription:
        return make_entity_description(
            entry_id=entry_id,
            domain="light",
            sandbox_entity_id=sandbox_entity_id,
            unique_id="1",
            supported_features=0,
            capabilities={"supported_color_modes": ["onoff"]},
            initial_state=STATE_ON,
            initial_attributes={"color_mode": "onoff"},
        )

    try:
        result_a = await sandbox_channel.call(
            "sandbox/register_entity", _payload(entry_a.entry_id, "light.a")
        )
        result_b = await sandbox_channel.call(
            "sandbox/register_entity", _payload(entry_b.entry_id, "light.b")
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    # Both proxies landed as distinct entities.
    assert result_a.entity_id != result_b.entity_id
    assert hass.states.get(result_a.entity_id) is not None
    assert hass.states.get(result_b.entity_id) is not None

    # Registry rows carry the domain-prefixed unique_ids, not a bare "1".
    assert entity_registry.async_get(result_a.entity_id).unique_id == "demo_a:1"
    assert entity_registry.async_get(result_b.entity_id).unique_id == "demo_b:1"


async def test_register_entity_upsert_updates_name_in_place(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A re-sent registration updates the proxy without adding a duplicate."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    def _payload(name: str) -> pb.EntityDescription:
        return make_entity_description(
            entry_id=entry.entry_id,
            domain="light",
            sandbox_entity_id="light.lamp",
            unique_id="lamp",
            name=name,
            supported_features=0,
            capabilities={"supported_color_modes": ["onoff"]},
            initial_state=STATE_ON,
            initial_attributes={"color_mode": "onoff"},
        )

    try:
        first = await sandbox_channel.call(
            "sandbox/register_entity", _payload("Old Name")
        )
        second = await sandbox_channel.call(
            "sandbox/register_entity", _payload("New Name")
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    # Same entity_id back, single tracked proxy — no duplicate created.
    assert first.entity_id == second.entity_id
    assert len(bridge._entities) == 1
    proxy = bridge._entities["light.lamp"]
    assert proxy._attr_name == "New Name"
    state = hass.states.get(second.entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == "New Name"


async def test_register_entity_upsert_refreshes_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A re-sent registration with new device_info updates the device entry."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    def _payload(sw_version: str) -> pb.EntityDescription:
        return make_entity_description(
            entry_id=entry.entry_id,
            domain="light",
            sandbox_entity_id="light.lamp",
            unique_id="lamp",
            supported_features=0,
            capabilities={"supported_color_modes": ["onoff"]},
            initial_state=STATE_ON,
            initial_attributes={"color_mode": "onoff"},
            device_info={
                "identifiers": [["demo", "dev-1"]],
                "name": "Lamp Device",
                "sw_version": sw_version,
            },
        )

    try:
        await sandbox_channel.call("sandbox/register_entity", _payload("1.0"))
        device = device_registry.async_get_device(identifiers={("demo", "dev-1")})
        assert device is not None
        assert device.sw_version == "1.0"

        await sandbox_channel.call("sandbox/register_entity", _payload("2.0"))
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    # Same device entry, firmware refreshed, single proxy — no duplicate.
    device = device_registry.async_get_device(identifiers={("demo", "dev-1")})
    assert device is not None
    assert device.sw_version == "2.0"
    assert len(bridge._entities) == 1


async def test_state_changed_push_updates_proxy(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A subsequent ``state_changed`` push updates the proxy's cache."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    register = make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id="light.lamp",
        unique_id="sandbox-lamp",
        supported_features=0,
        # Brightness color mode so the light surfaces ``brightness`` as
        # a first-class attribute when on.
        capabilities={"supported_color_modes": ["brightness"]},
        initial_state="off",
        initial_attributes={},
    )
    try:
        result = await sandbox_channel.call("sandbox/register_entity", register)
        state_changed = pb.StateChanged(sandbox_entity_id="light.lamp", state=STATE_ON)
        state_changed.attributes = encode_json(
            {"brightness": 250, "color_mode": "brightness"}
        )
        await sandbox_channel.push("sandbox/state_changed", state_changed)
        # Give the push handler a tick to land.
        for _ in range(20):
            state = hass.states.get(result.entity_id)
            if state is not None and state.state == STATE_ON:
                break
            await asyncio.sleep(0)
        state = hass.states.get(result.entity_id)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 250
    # Verify the cache was updated too (via the proxy directly).
    proxy = bridge._entities["light.lamp"]
    assert proxy.brightness == 250


async def test_proxy_method_translates_to_call_service(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Calling ``light.turn_on`` on a proxy fires one ``call_service`` RPC."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    calls: list[pb.CallService] = []

    async def _on_call_service(payload: pb.CallService) -> Any:
        calls.append(payload)
        return None

    sandbox_channel.register("sandbox/call_service", _on_call_service)

    register = make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id="light.bedroom",
        unique_id="sandbox-bedroom",
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
        initial_state="off",
        initial_attributes={},
    )
    try:
        result = await sandbox_channel.call("sandbox/register_entity", register)
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": result.entity_id},
            blocking=True,
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert len(calls) == 1
    assert calls[0].domain == "light"
    assert calls[0].service == "turn_on"
    assert decode_json_dict(calls[0].target) == {"entity_id": ["light.bedroom"]}


async def test_proxy_method_concurrent_calls_each_own_rpc(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Each proxy method call forwards as its own single-entity ``call_service``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    calls: list[pb.CallService] = []

    async def _on_call_service(payload: pb.CallService) -> Any:
        calls.append(payload)
        return None

    sandbox_channel.register("sandbox/call_service", _on_call_service)

    sandbox_ids = []
    try:
        for idx in range(5):
            register = make_entity_description(
                entry_id=entry.entry_id,
                domain="light",
                sandbox_entity_id=f"light.bulb_{idx}",
                unique_id=f"sandbox-bulb-{idx}",
                supported_features=0,
                capabilities={"supported_color_modes": ["onoff"]},
                initial_state="off",
                initial_attributes={},
            )
            await sandbox_channel.call("sandbox/register_entity", register)
            sandbox_ids.append(f"light.bulb_{idx}")

        async def _invoke(sandbox_id: str) -> None:
            proxy = bridge._entities[sandbox_id]
            await proxy.async_turn_on()

        await asyncio.gather(*(_invoke(sid) for sid in sandbox_ids))
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    # One RPC per entity call (no coalescing in the first iteration).
    assert len(calls) == len(sandbox_ids)
    assert all(c.domain == "light" and c.service == "turn_on" for c in calls)
    targeted = sorted(decode_json_dict(c.target)["entity_id"][0] for c in calls)
    assert targeted == sorted(sandbox_ids)


async def test_proxy_method_exception_translated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """``vol.Invalid`` on the sandbox side surfaces as ``TypeError`` on main."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    async def _on_call_service(_payload: dict[str, Any]) -> Any:
        raise ChannelRemoteError("bad kwarg", error_type="Invalid")

    # The Channel framework already wraps handler exceptions in error
    # frames, but our test stub raises ChannelRemoteError to simulate an
    # error frame coming back from the sandbox. Patch the channel's call
    # to fake the error response directly.
    async def _fake_call(*_args: Any, **_kwargs: Any) -> Any:
        raise ChannelRemoteError("bad kwarg", error_type="Invalid")

    main_channel.call = _fake_call  # type: ignore[method-assign]

    register = make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id="light.error",
        unique_id="sandbox-error",
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
        initial_state="off",
        initial_attributes={},
    )
    try:
        # Register goes through the call path too, so register before we
        # patch out the channel.
        pass
    finally:
        pass

    # We need to test the bridge's direct call path; build the proxy by
    # hand instead of going through register_entity.
    description = SandboxEntityDescription.from_proto(register)
    proxy_cls = (await bridge._async_build_proxy(description)).__class__
    proxy = proxy_cls(bridge, description)

    try:
        with pytest.raises(TypeError, match="bad kwarg"):
            await proxy.async_turn_on()
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_unknown_service_translated_to_home_assistant_error(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """``ServiceNotFound`` from the sandbox is surfaced as HomeAssistantError."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    async def _fake_call(*_args: Any, **_kwargs: Any) -> Any:
        raise ChannelRemoteError(
            "no such service light.party_mode", error_type="ServiceNotFound"
        )

    main_channel.call = _fake_call  # type: ignore[method-assign]

    description = SandboxEntityDescription(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id="light.x",
        unique_id="x",
    )
    proxy_cls = (await bridge._async_build_proxy(description)).__class__
    proxy = proxy_cls(bridge, description)

    try:
        with pytest.raises(HomeAssistantError, match="party_mode"):
            await proxy.async_turn_on()
    finally:
        await main_channel.close()
        await sandbox_channel.close()


def test_translate_remote_error_rebuilds_vol_invalid() -> None:
    """``error_data`` rebuilds a real ``vol.Invalid`` with its path intact."""
    err = ChannelRemoteError(
        "expected int",
        error_type="Invalid",
        error_data={
            "kind": "invalid",
            "msg": "expected int",
            "path": ["options", "count"],
        },
    )

    result = translate_remote_error(err)

    assert isinstance(result, vol.Invalid)
    assert not isinstance(result, vol.MultipleInvalid)
    assert result.error_message == "expected int"
    assert result.path == ["options", "count"]


def test_translate_remote_error_rebuilds_multiple_invalid() -> None:
    """``error_data`` rebuilds a ``vol.MultipleInvalid`` with its children."""
    err = ChannelRemoteError(
        "two problems",
        error_type="MultipleInvalid",
        error_data={
            "kind": "multiple",
            "errors": [
                {"kind": "invalid", "msg": "expected int", "path": ["count"]},
                {"kind": "invalid", "msg": "required key", "path": ["name"]},
            ],
        },
    )

    result = translate_remote_error(err)

    assert isinstance(result, vol.MultipleInvalid)
    assert [(child.error_message, child.path) for child in result.errors] == [
        ("expected int", ["count"]),
        ("required key", ["name"]),
    ]


def test_translate_remote_error_falls_back_without_error_data() -> None:
    """Frames without ``error_data`` keep the legacy class-name mapping."""
    err = ChannelRemoteError("bad kwarg", error_type="Invalid")

    result = translate_remote_error(err)

    assert isinstance(result, TypeError)
    assert str(result) == "bad kwarg"


async def test_register_entity_for_unknown_entry_raises(
    hass: HomeAssistant,
) -> None:
    """An unknown ``entry_id`` rejects the registration."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    try:
        with pytest.raises(ChannelRemoteError):
            await sandbox_channel.call(
                "sandbox/register_entity",
                make_entity_description(
                    entry_id="no-such-entry",
                    domain="light",
                    sandbox_entity_id="light.ghost",
                ),
            )
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_register_entity_auto_loads_domain_component(
    hass: HomeAssistant,
) -> None:
    """The bridge spins up the host EntityComponent for unfamiliar domains."""
    # `switch` is a different domain than the entry's owner (`light`) —
    # registering a switch proxy must trigger ``async_setup_component``.
    entry = MockConfigEntry(domain="generic", title="Generic", sandbox="built-in")
    entry.add_to_hass(hass)
    # Ensure switch isn't pre-loaded by the test fixture chain.
    assert "switch" not in hass.config.components

    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        result = await sandbox_channel.call(
            "sandbox/register_entity",
            make_entity_description(
                entry_id=entry.entry_id,
                domain="switch",
                sandbox_entity_id="switch.outlet",
                unique_id="sandbox-outlet",
                supported_features=0,
                capabilities={},
                initial_state="off",
                initial_attributes={},
            ),
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.entity_id.startswith("switch.")
    assert "switch" in hass.config.components


async def test_register_service_installs_forwarder(hass: HomeAssistant) -> None:
    """A sandbox-registered service appears on main and forwards calls back."""
    MockConfigEntry(
        domain="mirror_demo", title="Mirror", sandbox="built-in"
    ).add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    seen_calls: list[pb.CallService] = []

    async def _on_call_service(payload: pb.CallService) -> Any:
        seen_calls.append(payload)
        return None

    sandbox_channel.register("sandbox/call_service", _on_call_service)

    try:
        result = await sandbox_channel.call(
            "sandbox/register_service",
            pb.RegisterService(
                domain="mirror_demo",
                service="do_thing",
                supports_response="none",
            ),
        )
        assert result.installed is True
        assert hass.services.has_service("mirror_demo", "do_thing")

        await hass.services.async_call(
            "mirror_demo", "do_thing", {"foo": "bar"}, blocking=True
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert len(seen_calls) == 1
    assert seen_calls[0].domain == "mirror_demo"
    assert seen_calls[0].service == "do_thing"
    assert decode_json_dict(seen_calls[0].service_data) == {"foo": "bar"}


async def test_forwarded_context_restores_on_echoed_state(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A user's Context flows main → sandbox → back and is restored verbatim.

    Main forwards a service call carrying a real user Context into the
    sandbox; the bridge remembers it. When the sandbox emits a state change
    echoing that same context_id, main restores the *original*
    ``user_id`` / ``parent_id`` instead of minting a fresh attribution.
    """
    MockConfigEntry(
        domain="mirror_demo", title="Mirror", sandbox="built-in"
    ).add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    forwarded_ids: list[str] = []

    async def _on_call_service(payload: pb.CallService) -> Any:
        # Capture the context_id main handed down so we can echo it back.
        forwarded_ids.append(payload.context_id)
        return None

    sandbox_channel.register("sandbox/call_service", _on_call_service)

    try:
        # A proxy entity the echoed state change targets.
        register = await sandbox_channel.call(
            "sandbox/register_entity",
            make_entity_description(
                entry_id=entry.entry_id,
                domain="light",
                sandbox_entity_id="light.lamp",
                unique_id="sandbox-lamp",
                supported_features=0,
                capabilities={"supported_color_modes": ["onoff"]},
                initial_state="off",
                initial_attributes={"color_mode": "onoff"},
            ),
        )
        entity_id = register.entity_id
        # A mirrored service whose forwarder seeds the context cache.
        await sandbox_channel.call(
            "sandbox/register_service",
            pb.RegisterService(
                domain="mirror_demo", service="do_thing", supports_response="none"
            ),
        )

        # The user who pressed the button that triggered the sandboxed action.
        user_context = Context(user_id="user-1", parent_id="parent-1")
        await hass.services.async_call(
            "mirror_demo", "do_thing", {}, blocking=True, context=user_context
        )
        assert forwarded_ids == [user_context.id]

        # The sandboxed action emits a state change echoing that context_id.
        changed = pb.StateChanged(
            sandbox_entity_id="light.lamp", state="on", context_id=user_context.id
        )
        changed.attributes = encode_json({"color_mode": "onoff"})
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
    # The original attribution survived the round-trip — not a fresh context.
    assert state.context is user_context
    assert state.context.user_id == "user-1"
    assert state.context.parent_id == "parent-1"


async def test_register_service_skips_existing_handler(
    hass: HomeAssistant,
) -> None:
    """Main already owning ``(domain, service)`` is not clobbered."""
    MockConfigEntry(
        domain="mirror_local", title="Mirror", sandbox="built-in"
    ).add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    async def _local(_call: Any) -> None:
        return None

    hass.services.async_register("mirror_local", "noop", _local)

    try:
        result = await sandbox_channel.call(
            "sandbox/register_service",
            pb.RegisterService(
                domain="mirror_local",
                service="noop",
                supports_response="none",
            ),
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.installed is False
    # The existing handler is still in place — the bridge didn't replace it.
    assert hass.services.has_service("mirror_local", "noop")


async def test_unregister_service_removes_forwarder(
    hass: HomeAssistant,
) -> None:
    """``unregister_service`` drops the bridge-installed forwarder."""
    MockConfigEntry(
        domain="mirror_demo", title="Mirror", sandbox="built-in"
    ).add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    try:
        await sandbox_channel.call(
            "sandbox/register_service",
            pb.RegisterService(
                domain="mirror_demo",
                service="stop",
                supports_response="none",
            ),
        )
        assert hass.services.has_service("mirror_demo", "stop")

        result = await sandbox_channel.call(
            "sandbox/unregister_service",
            pb.UnregisterService(domain="mirror_demo", service="stop"),
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.removed is True
    assert not hass.services.has_service("mirror_demo", "stop")


async def test_fire_event_lands_on_main_bus(hass: HomeAssistant) -> None:
    """``fire_event`` re-fires the event on main's bus."""
    # The group owns the ``zha`` integration, so ``zha_event`` is in an owned
    # ``<domain>_`` namespace and passes the main-side fire_event gate.
    owner = MockConfigEntry(domain="zha", title="ZHA", sandbox="built-in")
    owner.add_to_hass(hass)

    _bridge, main_channel, sandbox_channel = await _wire(hass)

    received: list[Any] = []

    @callback
    def _on_zha(event: Any) -> None:
        received.append(event.data)

    hass.bus.async_listen("zha_event", _on_zha)

    try:
        fire_event = pb.FireEvent(event_type="zha_event")
        fire_event.event_data = encode_json(
            {"command": "on", "device_ieee": "0a:0b:0c"}
        )
        await sandbox_channel.push("sandbox/fire_event", fire_event)
        # Give the push handler a tick to run.
        for _ in range(20):
            if received:
                break
            await asyncio.sleep(0)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert received == [{"command": "on", "device_ieee": "0a:0b:0c"}]


# ---------------------------------------------------------------------------
# Adversarial / forged-frame gates (trust-boundary hardening)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        "homeassistant_stop",  # hard-denied core event
        "call_service",  # hard-denied core event
        "state_changed",  # hard-denied core event
        "zha_event",  # unowned domain — group owns nothing here
        "hue_event",  # unowned domain
    ],
)
async def test_fire_event_forged_type_dropped(
    hass: HomeAssistant, event_type: str
) -> None:
    """A compromised sandbox cannot fire core/foreign events on main's bus."""
    # The group owns only ``demo`` — nothing that namespaces the forged events.
    MockConfigEntry(domain="demo", title="Demo", sandbox="built-in").add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    received: list[Any] = []

    @callback
    def _listener(event: Any) -> None:
        received.append(event)

    hass.bus.async_listen(event_type, _listener)

    try:
        forged = pb.FireEvent(event_type=event_type)
        forged.event_data = encode_json({"injected": True})
        await sandbox_channel.push("sandbox/fire_event", forged)
        # Let the push handler run; the event must never reach the bus.
        for _ in range(20):
            await asyncio.sleep(0)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert received == []


async def test_register_service_unowned_domain_rejected(
    hass: HomeAssistant,
) -> None:
    """A sandbox cannot register a service in a domain it doesn't own."""
    # The group owns ``demo``; ``persistent_notification`` is not its to claim.
    MockConfigEntry(domain="demo", title="Demo", sandbox="built-in").add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    try:
        with pytest.raises(ChannelRemoteError, match="not owned by group"):
            await sandbox_channel.call(
                "sandbox/register_service",
                pb.RegisterService(
                    domain="persistent_notification",
                    service="create",
                    supports_response="none",
                ),
            )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert not hass.services.has_service("persistent_notification", "create")


async def test_register_entity_foreign_entry_rejected(
    hass: HomeAssistant,
) -> None:
    """A sandbox cannot attach entities to an entry routed to another group."""
    # The entry belongs to a *different* sandbox group than this bridge's.
    foreign = MockConfigEntry(domain="light", title="Victim", sandbox="other-group")
    foreign.add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)  # group="built-in"

    try:
        with pytest.raises(ChannelRemoteError, match="not owned by group"):
            await sandbox_channel.call(
                "sandbox/register_entity",
                make_entity_description(
                    entry_id=foreign.entry_id,
                    domain="light",
                    sandbox_entity_id="light.victim",
                ),
            )
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_register_entity_foreign_device_merge_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A sandbox cannot merge into a device owned by a foreign config entry."""
    # A victim integration owns a device with identifier ("victim", "dev-1").
    victim = MockConfigEntry(domain="victim", title="Victim")
    victim.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=victim.entry_id,
        identifiers={("victim", "dev-1")},
        name="Victim Device",
    )

    # The sandbox owns its own entry but forges device_info colliding with the
    # victim's identifiers to try to graft onto its device.
    owned = MockConfigEntry(domain="light", title="Owned", sandbox="built-in")
    owned.add_to_hass(hass)
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    try:
        with pytest.raises(ChannelRemoteError, match="outside group"):
            await sandbox_channel.call(
                "sandbox/register_entity",
                make_entity_description(
                    entry_id=owned.entry_id,
                    domain="light",
                    sandbox_entity_id="light.evil",
                    unique_id="evil",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["onoff"]},
                    initial_state=STATE_ON,
                    initial_attributes={"color_mode": "onoff"},
                    device_info={"identifiers": [["victim", "dev-1"]]},
                ),
            )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    # The victim's device still belongs only to the victim entry.
    device = device_registry.async_get_device(identifiers={("victim", "dev-1")})
    assert device is not None
    assert device.config_entries == {victim.entry_id}


async def test_context_cache_bounded_under_id_flood(
    hass: HomeAssistant,
) -> None:
    """Resolving a flood of distinct unknown context_ids stays cache-bounded."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    try:
        # Each unknown id mints a fresh Context cached under that key; without
        # eviction on the resolve path this would grow without bound.
        for i in range(_CONTEXT_CACHE_MAX * 2):
            bridge._resolve_context(f"forged-{i}")
        assert len(bridge._contexts) <= _CONTEXT_CACHE_MAX
    finally:
        await main_channel.close()
        await sandbox_channel.close()
