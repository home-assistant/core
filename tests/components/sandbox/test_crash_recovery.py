"""Crash / restart recovery regression tests.

Guards the crash-recovery cluster:

* Phase 1 — a respawn tears the old bridge down so the fresh one
  re-registers entities without ``"has already been setup!"``.
* Phase 2 — a dead sandbox's proxies go unavailable, then recover.
* Phase 4 — unloading an entry while the sandbox is down still releases
  the main-side proxies + ``EntityComponent`` platform slot (no leak).
"""

import asyncio
from typing import cast

import pytest

from homeassistant.components.sandbox import SandboxData
from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import SandboxBridge
from homeassistant.components.sandbox.channel import Channel
from homeassistant.components.sandbox.manager import SandboxManager
from homeassistant.components.sandbox.messages import make_entity_description
from homeassistant.components.sandbox.router import SandboxFlowRouter
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from ._helpers import FakeSandboxManager, make_channel_pair

from tests.common import MockConfigEntry

_SANDBOX_ENTITY_ID = "light.kitchen"


def _spawn_bridge(
    hass: HomeAssistant, *, name: str
) -> tuple[SandboxBridge, Channel, Channel]:
    """Wire one bridge incarnation to an in-memory channel-pair sandbox."""
    main_channel, sandbox_channel = make_channel_pair(
        name_a=f"main-{name}", name_b=f"sandbox-{name}"
    )
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()
    return bridge, main_channel, sandbox_channel


def _registration(entry: ConfigEntry) -> pb.EntityDescription:
    """A ``light.kitchen`` registration payload for ``entry``."""
    return make_entity_description(
        entry_id=entry.entry_id,
        domain="light",
        sandbox_entity_id=_SANDBOX_ENTITY_ID,
        unique_id="kitchen",
        name="Kitchen",
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
        initial_state=STATE_ON,
        # Light requires color_mode when ON.
        initial_attributes={"color_mode": "onoff"},
    )


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    """A sandbox-tagged light entry registered against ``hass``."""
    entry = MockConfigEntry(
        domain="light",
        title="Sandboxed Hue",
        data={"host": "1.2.3.4"},
        sandbox="built-in",
    )
    entry.add_to_hass(hass)
    return entry


async def test_crash_respawn_reregisters_entity(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A respawn re-registers an entity (no "has already been setup!")."""
    # First incarnation registers the entity.
    bridge1, main1, sandbox1 = _spawn_bridge(hass, name="1")
    payload = _registration(entry)
    result1 = await sandbox1.call("sandbox/register_entity", payload)
    entity_id = result1.entity_id
    assert hass.states.get(entity_id).state == STATE_ON

    # The sandbox crashes: the channel drops.
    await main1.close()
    await sandbox1.close()

    # Respawn: the keystone — tear the old bridge down so its
    # EntityComponent platform slot is released before the fresh process
    # re-registers the same entry.
    await bridge1.async_teardown()

    bridge2, main2, sandbox2 = _spawn_bridge(hass, name="2")
    try:
        result2 = await sandbox2.call("sandbox/register_entity", payload)
        # Live state still flows on the new bridge.
        update = pb.StateChanged(sandbox_entity_id=_SANDBOX_ENTITY_ID, state=STATE_OFF)
        update.attributes.update({"color_mode": "onoff"})
        await sandbox2.push("sandbox/state_changed", update)
        for _ in range(20):
            if hass.states.get(entity_id).state == STATE_OFF:
                break
            await asyncio.sleep(0)
    finally:
        await main2.close()
        await sandbox2.close()
        del bridge2

    # Re-registered cleanly and kept the same entity_id (same unique_id).
    assert result2.entity_id == entity_id
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_proxy_unavailable_when_sandbox_dies_then_recovers(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A dead sandbox's proxy goes unavailable, then recovers on respawn."""
    bridge1, main1, sandbox1 = _spawn_bridge(hass, name="1")
    result = await sandbox1.call("sandbox/register_entity", _registration(entry))
    entity_id = result.entity_id
    assert hass.states.get(entity_id).state == STATE_ON

    # Sandbox dies — the on_channel_closed path marks proxies unavailable.
    bridge1.async_mark_all_unavailable()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await main1.close()
    await sandbox1.close()
    await bridge1.async_teardown()

    # Respawn re-registers → back to available with live state.
    bridge2, main2, sandbox2 = _spawn_bridge(hass, name="2")
    try:
        await sandbox2.call("sandbox/register_entity", _registration(entry))
    finally:
        await main2.close()
        await sandbox2.close()
        del bridge2

    assert hass.states.get(entity_id).state == STATE_ON


async def test_unload_while_down_releases_platform(hass: HomeAssistant) -> None:
    """Unloading while the sandbox is down still releases the platform."""
    entry = MockConfigEntry(
        domain="light",
        title="Sandboxed Hue",
        data={"host": "1.2.3.4"},
        sandbox="built-in",
    )
    entry.add_to_hass(hass)

    # Register an entity (creates the EntityComponent platform slot).
    bridge, main1, sandbox1 = _spawn_bridge(hass, name="1")
    payload = _registration(entry)
    await sandbox1.call("sandbox/register_entity", payload)
    # Sandbox dies.
    await main1.close()
    await sandbox1.close()

    # The manager reports no live process for the group (sandbox down), so
    # the router skips the remote RPC but must still tear down main-side.
    data = SandboxData(bridges={"built-in": bridge})
    manager = FakeSandboxManager()
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager), data=data)

    unloaded = await router.async_unload_entry(entry)
    assert unloaded is True
    # Proxies + platform released — nothing leaked.
    assert bridge._entities == {}

    # A fresh bridge can re-register the same entry without colliding on the
    # "has already been setup!" guard.
    bridge2, main2, sandbox2 = _spawn_bridge(hass, name="2")
    try:
        result = await sandbox2.call("sandbox/register_entity", payload)
    finally:
        await main2.close()
        await sandbox2.close()
        del bridge2

    assert result.entity_id.startswith("light.")
