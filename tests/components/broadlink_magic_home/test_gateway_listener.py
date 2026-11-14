"""Tests for hass-level inbound gateway routing."""

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from broadlink_magic import (
    MSG_HEARTBEAT,
    Family,
    GatewaySet,
    ImportedDevice,
    pack_message,
)

from homeassistant.components.broadlink_magic_home.gateway_listener import (
    DATA_GATEWAY_LISTENER,
    GatewayListenerManager,
    async_get_gateway_listener,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant


class FakeTransport:
    """Capture listener replies."""

    def __init__(self) -> None:
        """Initialize an empty packet capture."""
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.closed = False

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        """Capture one UDP packet."""
        self.sent.append((data, addr))

    def close(self) -> None:
        """Record listener closure."""
        self.closed = True


def _gateway_set(mac: str, manager: GatewayListenerManager) -> GatewaySet:
    family = Family(
        family_id=mac,
        name=mac,
        bletoken="00010203",
        devices=[
            ImportedDevice(
                did=f"00000000000000000000{mac}",
                pid="0000000000000000000000008baf0000",
                name=mac,
                mac=mac,
            ),
            ImportedDevice(
                did=f"00000000000000000000{mac}",
                pid="",
                name="Light",
                sdid=f"{mac}_light",
                short_addr=257,
                ble_category="LIGHT",
            ),
        ],
    )
    return GatewaySet(family, sender=manager.registry.sendto)


async def test_multiple_entries_share_listener_and_unregister_independently(
    hass: HomeAssistant,
) -> None:
    """Test one registry isolates multiple config entries by gateway MAC."""
    manager = GatewayListenerManager(hass)
    transport = FakeTransport()
    manager.registry.transport = cast(Any, transport)
    first = _gateway_set("aabbccddeeff", manager)
    second = _gateway_set("112233445566", manager)
    first_updates = 0
    second_updates = 0

    def update_first() -> None:
        nonlocal first_updates
        first_updates += 1

    def update_second() -> None:
        nonlocal second_updates
        second_updates += 1

    manager.register_gateway_set("first", first, update_first)
    manager.register_gateway_set("second", second, update_second)
    manager.registry.datagram_received(
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    manager.registry.datagram_received(
        pack_message(MSG_HEARTBEAT, 2, bytes.fromhex("112233445566")),
        ("192.0.2.11", 41002),
    )
    await hass.async_block_till_done()
    assert first_updates == second_updates == 1
    assert first.online_gateways[0].peer == ("192.0.2.10", 41001)
    assert second.online_gateways[0].peer == ("192.0.2.11", 41002)
    assert any(
        int.from_bytes(packet[:2], "little") == 17 for packet, _ in transport.sent
    )

    await manager.async_unregister_entry("first")
    manager.registry.datagram_received(
        pack_message(MSG_HEARTBEAT, 3, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 42001),
    )
    manager.registry.datagram_received(
        pack_message(MSG_HEARTBEAT, 4, bytes.fromhex("112233445566")),
        ("192.0.2.11", 42002),
    )
    await hass.async_block_till_done()
    assert first_updates == 1
    assert second_updates == 2
    await manager.async_unregister_entry("second")
    assert transport.closed


async def test_concurrent_getters_bind_once(hass: HomeAssistant) -> None:
    """Test setups racing for the listener share one bound socket."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_start() -> None:
        await _wait(started, release)

    start = AsyncMock(side_effect=fake_start)
    with patch.object(GatewayListenerManager, "async_start", start):
        first = hass.async_create_task(async_get_gateway_listener(hass))
        second = hass.async_create_task(async_get_gateway_listener(hass))
        await started.wait()
        await asyncio.sleep(0)
        release.set()
        managers = await asyncio.gather(first, second)
    assert start.await_count == 1
    assert managers[0] is managers[1]


async def test_getter_waits_for_closing_listener(hass: HomeAssistant) -> None:
    """Test a setup during the last unload binds a fresh listener."""
    with patch.object(GatewayListenerManager, "async_start", AsyncMock()):
        old = await async_get_gateway_listener(hass)
    old.register_gateway_set("old", _gateway_set("aabbccddeeff", old), lambda: None)
    closing = asyncio.Event()
    release = asyncio.Event()

    async def fake_close() -> None:
        await _wait(closing, release)

    with patch.object(old.registry, "async_close", AsyncMock(side_effect=fake_close)):
        unload = hass.async_create_task(old.async_unregister_entry("old"))
        await closing.wait()
        with patch.object(GatewayListenerManager, "async_start", AsyncMock()):
            getter = hass.async_create_task(async_get_gateway_listener(hass))
            await asyncio.sleep(0)
            assert not getter.done()
            release.set()
            await unload
            new = await getter
    assert new is not old
    assert hass.data[DATA_GATEWAY_LISTENER] is new


async def test_gateway_mac_routes_to_one_entry(hass: HomeAssistant) -> None:
    """Test a gateway MAC owned by one entry is not taken over by another."""
    manager = GatewayListenerManager(hass)
    manager.registry.transport = cast(Any, FakeTransport())
    first = _gateway_set("aabbccddeeff", manager)
    second = _gateway_set("aabbccddeeff", manager)
    manager.register_gateway_set("first", first, lambda: None)
    manager.register_gateway_set("second", second, lambda: None)

    await manager.async_unregister_entry("second")
    manager.registry.datagram_received(
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    assert first.online_gateways
    assert not second.online_gateways


async def test_stop_listener_follows_listener_lifetime(hass: HomeAssistant) -> None:
    """Test the stop listener is removed on close and closes on stop."""
    listeners = hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0)
    closed = GatewayListenerManager(hass)
    with patch.object(closed.registry, "async_start", AsyncMock()):
        await closed.async_start()
    assert hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STOP] == listeners + 1
    await closed.async_close()
    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0) == listeners

    running = GatewayListenerManager(hass)
    with (
        patch.object(running.registry, "async_start", AsyncMock()),
        patch.object(running.registry, "async_close", AsyncMock()) as close,
    ):
        await running.async_start()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    close.assert_awaited_once()


async def _wait(started: asyncio.Event, release: asyncio.Event) -> None:
    started.set()
    await release.wait()
