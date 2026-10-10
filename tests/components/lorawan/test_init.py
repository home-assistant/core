"""Connection registration, vendor discovery, and subscription cleanup."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

from lorawan_connection import ConnectionUnavailable, DeviceEvent, Downlink, EventType
from lorawan_connection.mock import MockConnection
import pytest

from homeassistant.components.lorawan import (
    async_get_connections,
    async_register_connection,
    async_subscribe_connections,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import RegisterBackend
from .helpers import DESCRIPTOR, inventory

from tests.common import MockConfigEntry


async def test_subscribe_and_reconnect(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Consumers see current connections, withdrawals, and replacement transports."""
    first, unregister = await registered_backend("network", [DESCRIPTOR])
    changed = Mock()
    unsubscribe = async_subscribe_connections(hass, changed)
    changed.assert_called_once_with("network", first)
    assert async_get_connections(hass) == {"network": first}
    events = Mock()
    stop_events = await first.async_subscribe(
        brands=frozenset({("example", 123)}), callback=events
    )
    events.assert_called_once()
    first.emit(inventory(replace(DESCRIPTOR, name="Renamed"), EventType.UPDATED))
    assert events.call_count == 2
    queue_id = await first.async_send_downlink(
        Downlink(DESCRIPTOR.dev_eui, 1, b"command")
    )
    assert first.downlinks[queue_id].data == b"command"
    first.disconnect()
    changed.assert_called_with("network", None)
    assert async_get_connections(hass) == {}
    unregister()
    second, unregister_second = await registered_backend("network", [DESCRIPTOR])
    changed.assert_called_with("network", second)
    stop_events()
    unsubscribe()
    unsubscribe()
    unregister_second()
    assert changed.call_count == 3


async def test_discovery_replay_and_live_events(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Inventory deduplicates vendor discovery and later changes can rediscover it."""
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        backend, _ = await registered_backend(
            "network", [DESCRIPTOR, replace(DESCRIPTOR, dev_eui="0201010101010102")]
        )
        discover.assert_called_once_with(
            hass,
            "test_vendor",
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={},
        )
        backend.emit(inventory(DESCRIPTOR, EventType.UPDATED))
        assert discover.call_count == 2
        backend.emit(inventory(DESCRIPTOR, EventType.REMOVED))
        backend.emit(inventory(replace(DESCRIPTOR, brand_id=456)))
        assert discover.call_count == 2


async def test_duplicate_registration(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """An active provider cannot be replaced without withdrawal."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    entry = hass.config_entries.async_get_entry("network")
    with pytest.raises(ValueError, match="already registered"):
        await async_register_connection(hass, entry, connection=MockConnection())
    assert async_get_connections(hass) == {"network": backend}


@pytest.mark.parametrize(
    "error", [ConnectionUnavailable("offline"), asyncio.CancelledError()]
)
async def test_registration_failure(
    hass: HomeAssistant, provider_entry: MockConfigEntry, error: BaseException
) -> None:
    """Failure and cancellation clean up discovery and allow a later attempt."""
    assert await async_setup_component(hass, "lorawan", {})
    stop_disconnect = Mock()
    backend = Mock(
        on_disconnect=Mock(return_value=stop_disconnect),
        async_subscribe=AsyncMock(side_effect=error),
    )
    with pytest.raises(type(error)):
        await async_register_connection(hass, provider_entry, connection=backend)
    stop_disconnect.assert_called_once_with()
    assert not async_get_connections(hass)
    unsubscribe = await async_register_connection(
        hass, provider_entry, connection=MockConnection()
    )
    unsubscribe()


async def test_concurrent_registration(
    hass: HomeAssistant, provider_entry: MockConfigEntry
) -> None:
    """The entry is reserved while discovery inventory is being replayed."""
    assert await async_setup_component(hass, "lorawan", {})
    started, finish = asyncio.Event(), asyncio.Event()
    stop_events, stop_disconnect = Mock(), Mock()

    async def replay(
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        callback: Callable[[DeviceEvent], None],
    ) -> Mock:
        started.set()
        await finish.wait()
        return stop_events

    backend = Mock(
        on_disconnect=Mock(return_value=stop_disconnect),
        async_subscribe=AsyncMock(side_effect=replay),
    )
    registration = hass.async_create_task(
        async_register_connection(hass, provider_entry, connection=backend)
    )
    await started.wait()
    with pytest.raises(ValueError, match="already registered"):
        await async_register_connection(
            hass, provider_entry, connection=MockConnection()
        )
    finish.set()
    unsubscribe = await registration
    unsubscribe()
    stop_events.assert_called_once_with()
    stop_disconnect.assert_called_once_with()


async def test_disconnect_during_registration(
    hass: HomeAssistant, provider_entry: MockConfigEntry
) -> None:
    """A disconnect during replay cannot publish or discover a stale connection."""
    assert await async_setup_component(hass, "lorawan", {})
    stop_events, stop_disconnect = Mock(), Mock()
    backend = Mock(on_disconnect=Mock(return_value=stop_disconnect))

    async def replay(
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        callback: Callable[[DeviceEvent], None],
    ) -> Mock:
        callback(inventory())
        backend.on_disconnect.call_args.args[0]()
        return stop_events

    backend.async_subscribe = AsyncMock(side_effect=replay)
    with (
        patch(
            "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
        ) as discover,
        pytest.raises(ConnectionUnavailable),
    ):
        await async_register_connection(hass, provider_entry, connection=backend)
    discover.assert_not_called()
    stop_events.assert_called_once_with()
    stop_disconnect.assert_called_once_with()
    assert not async_get_connections(hass)


async def test_failed_listener_replay(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Initial callback errors release the listener before propagating."""
    await registered_backend("network", [])
    listener = Mock(side_effect=RuntimeError("observer failed"))
    with pytest.raises(RuntimeError, match="observer failed"):
        async_subscribe_connections(hass, listener)
    await registered_backend("other", [])
    listener.assert_called_once()


async def test_shutdown_releases_subscriptions(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """HA shutdown releases discovery without closing provider-owned transports."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    changed = Mock()
    async_subscribe_connections(hass, changed)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert not async_get_connections(hass)
    changed.assert_called_with("network", None)
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        backend.emit(inventory(DESCRIPTOR, EventType.UPDATED))
    discover.assert_not_called()
