"""Tests for the Phase 5 :class:`SandboxBridge` — main-side entity bridge."""

import asyncio
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.sandbox_v2.bridge import (
    SandboxBridge,
    SandboxEntityDescription,
    _translate_remote_error,
)
from homeassistant.components.sandbox_v2.channel import Channel, ChannelRemoteError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

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
    """Suppress strings.json checks for the Phase 6 mock domains."""
    return ["phase6_demo", "phase6_local"]


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    """A loaded MockConfigEntry registered against ``hass``."""
    entry = MockConfigEntry(
        domain="light", title="Sandboxed Hue", data={"host": "1.2.3.4"}
    )
    entry.add_to_hass(hass)
    return entry


async def test_register_entity_creates_proxy_and_returns_entity_id(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A ``register_entity`` push creates a live proxy on the right domain."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    payload = {
        "entry_id": entry.entry_id,
        "domain": "light",
        "sandbox_entity_id": "light.kitchen",
        "unique_id": "sandbox-kitchen",
        "name": "Kitchen",
        "supported_features": 0,
        "capabilities": {"supported_color_modes": ["onoff"]},
        "initial_state": STATE_ON,
        # Light requires color_mode when ON, so feed it through the
        # initial cache to keep state_attributes from raising.
        "initial_attributes": {"color_mode": "onoff"},
    }

    try:
        result = await sandbox_channel.call("sandbox_v2/register_entity", payload)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result["entity_id"].startswith("light.")
    state = hass.states.get(result["entity_id"])
    assert state is not None
    assert state.state == STATE_ON
    # The bridge tracks the proxy by its sandbox-side entity_id.
    assert "light.kitchen" in bridge._entities


async def test_state_changed_push_updates_proxy(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A subsequent ``state_changed`` push updates the proxy's cache."""
    bridge, main_channel, sandbox_channel = await _wire(hass)

    register = {
        "entry_id": entry.entry_id,
        "domain": "light",
        "sandbox_entity_id": "light.lamp",
        "unique_id": "sandbox-lamp",
        "supported_features": 0,
        # Brightness color mode so the light surfaces ``brightness`` as
        # a first-class attribute when on.
        "capabilities": {"supported_color_modes": ["brightness"]},
        "initial_state": "off",
        "initial_attributes": {},
    }
    try:
        result = await sandbox_channel.call("sandbox_v2/register_entity", register)
        await sandbox_channel.push(
            "sandbox_v2/state_changed",
            {
                "sandbox_entity_id": "light.lamp",
                "new_state": {
                    "state": STATE_ON,
                    "attributes": {"brightness": 250, "color_mode": "brightness"},
                },
            },
        )
        # Give the push handler a tick to land.
        for _ in range(20):
            state = hass.states.get(result["entity_id"])
            if state is not None and state.state == STATE_ON:
                break
            await asyncio.sleep(0)
        state = hass.states.get(result["entity_id"])
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
    calls: list[dict[str, Any]] = []

    async def _on_call_service(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        return None

    sandbox_channel.register("sandbox_v2/call_service", _on_call_service)

    register = {
        "entry_id": entry.entry_id,
        "domain": "light",
        "sandbox_entity_id": "light.bedroom",
        "unique_id": "sandbox-bedroom",
        "supported_features": 0,
        "capabilities": {"supported_color_modes": ["onoff"]},
        "initial_state": "off",
        "initial_attributes": {},
    }
    try:
        result = await sandbox_channel.call("sandbox_v2/register_entity", register)
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": result["entity_id"]},
            blocking=True,
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert len(calls) == 1
    assert calls[0]["domain"] == "light"
    assert calls[0]["service"] == "turn_on"
    assert calls[0]["target"] == {"entity_id": ["light.bedroom"]}


async def test_proxy_method_batches_concurrent_calls(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Many entities targeted in one tick coalesce into one ``call_service``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    calls: list[dict[str, Any]] = []

    async def _on_call_service(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        return None

    sandbox_channel.register("sandbox_v2/call_service", _on_call_service)

    sandbox_ids = []
    try:
        for idx in range(5):
            register = {
                "entry_id": entry.entry_id,
                "domain": "light",
                "sandbox_entity_id": f"light.bulb_{idx}",
                "unique_id": f"sandbox-bulb-{idx}",
                "supported_features": 0,
                "capabilities": {"supported_color_modes": ["onoff"]},
                "initial_state": "off",
                "initial_attributes": {},
            }
            await sandbox_channel.call("sandbox_v2/register_entity", register)
            sandbox_ids.append(f"light.bulb_{idx}")

        # Call turn_on on every proxy "simultaneously" (no awaits between
        # them) — the batcher should see all of them in the same tick.
        async def _invoke(sandbox_id: str) -> None:
            proxy = bridge._entities[sandbox_id]
            await proxy.async_turn_on()

        await asyncio.gather(*(_invoke(sid) for sid in sandbox_ids))
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert len(calls) == 1
    assert calls[0]["domain"] == "light"
    assert calls[0]["service"] == "turn_on"
    assert sorted(calls[0]["target"]["entity_id"]) == sorted(sandbox_ids)


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

    register = {
        "entry_id": entry.entry_id,
        "domain": "light",
        "sandbox_entity_id": "light.error",
        "unique_id": "sandbox-error",
        "supported_features": 0,
        "capabilities": {"supported_color_modes": ["onoff"]},
        "initial_state": "off",
        "initial_attributes": {},
    }
    try:
        # Register goes through the call path too, so register before we
        # patch out the channel.
        pass
    finally:
        pass

    # We need to test the bridge's direct call path; build the proxy by
    # hand instead of going through register_entity.
    description = SandboxEntityDescription.from_payload(register)
    proxy_cls = bridge._build_proxy(description).__class__
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
    proxy_cls = bridge._build_proxy(description).__class__
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

    result = _translate_remote_error(err)

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

    result = _translate_remote_error(err)

    assert isinstance(result, vol.MultipleInvalid)
    assert [(child.error_message, child.path) for child in result.errors] == [
        ("expected int", ["count"]),
        ("required key", ["name"]),
    ]


def test_translate_remote_error_falls_back_without_error_data() -> None:
    """Frames without ``error_data`` keep the legacy class-name mapping."""
    err = ChannelRemoteError("bad kwarg", error_type="Invalid")

    result = _translate_remote_error(err)

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
                "sandbox_v2/register_entity",
                {
                    "entry_id": "no-such-entry",
                    "domain": "light",
                    "sandbox_entity_id": "light.ghost",
                },
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
    entry = MockConfigEntry(domain="generic", title="Generic")
    entry.add_to_hass(hass)
    # Ensure switch isn't pre-loaded by the test fixture chain.
    assert "switch" not in hass.config.components

    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        result = await sandbox_channel.call(
            "sandbox_v2/register_entity",
            {
                "entry_id": entry.entry_id,
                "domain": "switch",
                "sandbox_entity_id": "switch.outlet",
                "unique_id": "sandbox-outlet",
                "supported_features": 0,
                "capabilities": {},
                "initial_state": "off",
                "initial_attributes": {},
            },
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result["entity_id"].startswith("switch.")
    assert "switch" in hass.config.components


async def test_register_service_installs_forwarder(hass: HomeAssistant) -> None:
    """A sandbox-registered service appears on main and forwards calls back."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    seen_calls: list[dict[str, Any]] = []

    async def _on_call_service(payload: dict[str, Any]) -> Any:
        seen_calls.append(payload)
        return None

    sandbox_channel.register("sandbox_v2/call_service", _on_call_service)

    try:
        result = await sandbox_channel.call(
            "sandbox_v2/register_service",
            {
                "domain": "phase6_demo",
                "service": "do_thing",
                "supports_response": "none",
            },
        )
        assert result["installed"] is True
        assert hass.services.has_service("phase6_demo", "do_thing")

        await hass.services.async_call(
            "phase6_demo", "do_thing", {"foo": "bar"}, blocking=True
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert len(seen_calls) == 1
    assert seen_calls[0]["domain"] == "phase6_demo"
    assert seen_calls[0]["service"] == "do_thing"
    assert seen_calls[0]["service_data"] == {"foo": "bar"}


async def test_register_service_skips_existing_handler(
    hass: HomeAssistant,
) -> None:
    """Main already owning ``(domain, service)`` is not clobbered."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    async def _local(_call: Any) -> None:
        return None

    hass.services.async_register("phase6_local", "noop", _local)

    try:
        result = await sandbox_channel.call(
            "sandbox_v2/register_service",
            {
                "domain": "phase6_local",
                "service": "noop",
                "supports_response": "none",
            },
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result["installed"] is False
    # The existing handler is still in place — the bridge didn't replace it.
    assert hass.services.has_service("phase6_local", "noop")


async def test_unregister_service_removes_forwarder(
    hass: HomeAssistant,
) -> None:
    """``unregister_service`` drops the bridge-installed forwarder."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    try:
        await sandbox_channel.call(
            "sandbox_v2/register_service",
            {
                "domain": "phase6_demo",
                "service": "stop",
                "supports_response": "none",
            },
        )
        assert hass.services.has_service("phase6_demo", "stop")

        result = await sandbox_channel.call(
            "sandbox_v2/unregister_service",
            {"domain": "phase6_demo", "service": "stop"},
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result["removed"] is True
    assert not hass.services.has_service("phase6_demo", "stop")


async def test_fire_event_lands_on_main_bus(hass: HomeAssistant) -> None:
    """``fire_event`` re-fires the event on main's bus."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)

    received: list[Any] = []

    @callback
    def _on_zha(event: Any) -> None:
        received.append(event.data)

    hass.bus.async_listen("zha_event", _on_zha)

    try:
        await sandbox_channel.push(
            "sandbox_v2/fire_event",
            {
                "event_type": "zha_event",
                "event_data": {"command": "on", "device_ieee": "0a:0b:0c"},
            },
        )
        # Give the push handler a tick to run.
        for _ in range(20):
            if received:
                break
            await asyncio.sleep(0)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert received == [{"command": "on", "device_ieee": "0a:0b:0c"}]
