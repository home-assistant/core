"""Tests for iTach IP2IR discovery helpers."""

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.itachip2ir.const import DOMAIN
from homeassistant.components.itachip2ir.discovery import (
    FLOW_THROTTLE_SECONDS,
    ItachDiscovery,
    async_discover_once,
    async_wait_for_device_id,
)
from homeassistant.components.itachip2ir.pyitach import ItachDiscoveryBeacon
from homeassistant.components.itachip2ir.pyitach._discovery import (
    _DISCOVERY_PORT as DISCOVERY_PORT,
    ItachDiscoveryListener,
    async_discover_once as pyitach_async_discover_once,
    normalize_host as _normalize_host,
    normalize_uuid as _normalize_uuid,
    parse_discovery_beacon as _parse_beacon,
)
from homeassistant.config_entries import SOURCE_DISCOVERY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "192.168.1.211"
OTHER_HOST = "192.168.1.212"
NEW_HOST = "192.168.1.250"
UNIQUE_ID = "GlobalCache_000C1E123456"


class FakeSocket:
    """Fake UDP socket."""

    def __init__(
        self,
        *,
        bind_error: OSError | None = None,
        multicast_error: OSError | None = None,
    ) -> None:
        """Initialize fake socket."""
        self.bind_error = bind_error
        self.multicast_error = multicast_error
        self.closed = False
        self.bound_address: tuple[str, int] | None = None
        self.blocking = True
        self.setsockopt_calls: list[tuple[int, int, object]] = []

    def setsockopt(self, level: int, option: int, value: object) -> None:
        """Record socket option calls."""
        self.setsockopt_calls.append((level, option, value))

        if level == socket.IPPROTO_IP and option == socket.IP_ADD_MEMBERSHIP:
            if self.multicast_error is not None:
                raise self.multicast_error

    def bind(self, address: tuple[str, int]) -> None:
        """Bind fake socket."""
        if self.bind_error is not None:
            raise self.bind_error

        self.bound_address = address

    def setblocking(self, blocking: bool) -> None:
        """Set fake blocking state."""
        self.blocking = blocking

    def close(self) -> None:
        """Close fake socket."""
        self.closed = True


def _beacon(
    *,
    host: str = HOST,
    uuid: str = UNIQUE_ID,
    model: str = "iTachIP2IR",
) -> str:
    """Return a fake Global Caché beacon payload."""
    return (
        "AMXB<-SDKClass=Utility>"
        "<-Make=GlobalCache>"
        f"<-Model={model}>"
        f"<-UUID={uuid}>"
        f"<-Config-URL=http://{host}.>"
    )


def test_parse_beacon_valid() -> None:
    """Test parsing a valid iTach beacon."""
    parsed = _parse_beacon(_beacon())

    assert parsed == ItachDiscoveryBeacon(
        host=HOST,
        uuid=UNIQUE_ID,
        model="iTachIP2IR",
    )


def test_parse_beacon_invalid_payload_returns_none() -> None:
    """Test invalid payloads are ignored."""
    assert _parse_beacon("not a global cache beacon") is None
    assert _parse_beacon("AMXB but missing vendor") is None


def test_parse_beacon_missing_fields_returns_none() -> None:
    """Test a Global Caché beacon with missing required fields is ignored."""
    assert _parse_beacon("AMXB<-Make=GlobalCache>") is None


def test_parse_beacon_without_config_url_uses_packet_host() -> None:
    """Test beacon without config URL uses packet host fallback."""
    parsed = _parse_beacon(
        f"AMXB<-Make=GlobalCache><-Model=iTachIP2IR><-UUID={UNIQUE_ID}>",
        HOST,
    )

    assert parsed == ItachDiscoveryBeacon(
        host=HOST,
        uuid=UNIQUE_ID,
        model="iTachIP2IR",
    )


async def test_pyitach_async_discover_once_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test one-shot hardware discovery returns None on timeout."""
    fake_socket = FakeSocket()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )

    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "sock_recvfrom",
        AsyncMock(side_effect=asyncio.TimeoutError),
    )

    assert await pyitach_async_discover_once(timeout=0.1) is None
    assert fake_socket.closed


async def test_pyitach_async_discover_once_valid_beacon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test one-shot hardware discovery returns a valid beacon."""
    fake_socket = FakeSocket()
    loop = asyncio.get_running_loop()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )
    monkeypatch.setattr(
        loop,
        "sock_recvfrom",
        AsyncMock(return_value=(_beacon().encode(), (HOST, DISCOVERY_PORT))),
    )

    result = await pyitach_async_discover_once(timeout=1.0)

    assert result == ItachDiscoveryBeacon(
        host=HOST,
        uuid=UNIQUE_ID,
        model="iTachIP2IR",
    )
    assert fake_socket.bound_address == ("", DISCOVERY_PORT)
    assert not fake_socket.blocking
    assert fake_socket.closed


async def test_pyitach_async_discover_once_malformed_beacon_then_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test hardware discovery ignores malformed beacons and then times out."""
    fake_socket = FakeSocket()
    loop = asyncio.get_running_loop()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )
    monkeypatch.setattr(
        loop,
        "sock_recvfrom",
        AsyncMock(
            side_effect=[
                (b"not a global cache beacon", (HOST, DISCOVERY_PORT)),
                asyncio.TimeoutError,
            ],
        ),
    )

    assert await pyitach_async_discover_once(timeout=1.0) is None
    assert fake_socket.closed


async def test_pyitach_async_discover_once_ignores_missing_uuid_then_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test hardware discovery ignores beacons missing UUID."""
    fake_socket = FakeSocket()
    loop = asyncio.get_running_loop()

    message = f"AMXB<-Make=GlobalCache><-Model=iTachIP2IR><-Config-URL=http://{HOST}.>"

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )
    monkeypatch.setattr(
        loop,
        "sock_recvfrom",
        AsyncMock(
            side_effect=[
                (message.encode(), (HOST, DISCOVERY_PORT)),
                asyncio.TimeoutError,
            ],
        ),
    )

    assert await pyitach_async_discover_once(timeout=1.0) is None
    assert fake_socket.closed


async def test_pyitach_async_discover_once_socket_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test hardware one-shot discovery handles socket setup errors."""
    fake_socket = FakeSocket(bind_error=OSError("bind failed"))

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )

    assert await pyitach_async_discover_once(timeout=1.0) is None
    assert fake_socket.closed


async def test_async_discover_once_filters_non_ip2ir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HA wrapper filters non-IP2IR Global Caché beacons."""

    async def fake_discover_once(timeout: float):
        return ItachDiscoveryBeacon(
            host=HOST,
            uuid=UNIQUE_ID,
            model="iTachIP2SL",
        )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery._async_discover_once",
        fake_discover_once,
    )

    assert await async_discover_once(timeout=1.0) is None


async def test_async_discover_once_returns_ip2ir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HA wrapper returns discovered IP2IR data."""

    async def fake_discover_once(timeout: float):
        return ItachDiscoveryBeacon(
            host=HOST,
            uuid=UNIQUE_ID,
            model="iTachIP2IR",
        )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery._async_discover_once",
        fake_discover_once,
    )

    assert await async_discover_once(timeout=1.0) == {
        "host": HOST,
        "uuid": UNIQUE_ID,
        "model": "iTachIP2IR",
    }


async def test_async_wait_for_device_id_returns_matching_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for a matching host returns the discovered UUID."""

    async def fake_discover_once(timeout: float):
        return {
            "host": HOST,
            "uuid": UNIQUE_ID,
            "model": "iTachIP2IR",
        }

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        fake_discover_once,
    )

    assert await async_wait_for_device_id(HOST, timeout=10.0) == UNIQUE_ID


async def test_async_wait_for_device_id_returns_none_for_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for device ID returns None when discovery finds nothing."""

    async def fake_discover_once(timeout: float):
        return None

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        fake_discover_once,
    )

    assert await async_wait_for_device_id(HOST) is None


async def test_async_wait_for_device_id_returns_none_for_host_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for device ID ignores beacons from another host."""

    async def fake_discover_once(timeout: float):
        return {
            "host": OTHER_HOST,
            "uuid": UNIQUE_ID,
            "model": "iTachIP2IR",
        }

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        fake_discover_once,
    )

    assert await async_wait_for_device_id(HOST) is None


def test_known_device_id_lookup(hass: HomeAssistant) -> None:
    """Test known device ID lookup."""
    discovery = ItachDiscovery(hass)

    assert discovery.get_known_device_id(HOST) is None

    discovery._known_devices[HOST] = UNIQUE_ID

    assert discovery.get_known_device_id(HOST) == UNIQUE_ID


def test_is_already_configured_false(hass: HomeAssistant) -> None:
    """Test _is_already_configured returns false when entry is unknown."""
    discovery = ItachDiscovery(hass)

    assert not discovery._is_already_configured(UNIQUE_ID)


def test_is_already_configured_true(hass: HomeAssistant) -> None:
    """Test _is_already_configured returns true for configured unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title="iTach IP2IR",
    )
    entry.add_to_hass(hass)

    discovery = ItachDiscovery(hass)

    assert discovery._is_already_configured(UNIQUE_ID)


def test_configured_device_host_update(hass: HomeAssistant) -> None:
    """Test discovery updates host for an already configured entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        title="iTach IP2IR (192.168.1.100)",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)
    schedule_reload.assert_not_called()

    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == HOST
    assert entry.data["port"] == 4998
    assert entry.title == f"iTach IP2IR ({HOST})"
    schedule_reload.assert_called_once_with(entry.entry_id)


def test_configured_device_host_update_preserves_custom_title(
    hass: HomeAssistant,
) -> None:
    """Test discovery host update preserves user/custom entry title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        title="Living Room iTach",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)
    schedule_reload.assert_not_called()

    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == HOST
    assert entry.title == "Living Room iTach"
    schedule_reload.assert_called_once_with(entry.entry_id)


def test_configured_device_host_update_skips_options_override(
    hass: HomeAssistant,
) -> None:
    """Test discovery does not update host when options override host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        options={"host": "192.168.1.250"},
        title="iTach IP2IR",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == "192.168.1.100"
    schedule_reload.assert_not_called()


def test_configured_device_host_update_skips_unchanged_host(
    hass: HomeAssistant,
) -> None:
    """Test discovery skips update when host has not changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title=f"iTach IP2IR ({HOST})",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == HOST
    schedule_reload.assert_not_called()


def test_configured_device_host_update_requires_same_host_confirmation(
    hass: HomeAssistant,
) -> None:
    """Test host update confirmation resets when discovered host changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        title="iTach IP2IR (192.168.1.100)",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)
    discovery._update_configured_host(entry, OTHER_HOST)

    assert entry.data["host"] == "192.168.1.100"
    schedule_reload.assert_not_called()

    discovery._update_configured_host(entry, OTHER_HOST)

    assert entry.data["host"] == OTHER_HOST
    schedule_reload.assert_called_once_with(entry.entry_id)


def test_flow_throttle(monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant) -> None:
    """Test discovery flow throttling."""
    discovery = ItachDiscovery(hass)

    now = 1000.0
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.time.monotonic",
        lambda: now,
    )

    assert not discovery._is_flow_throttled(UNIQUE_ID)

    discovery._mark_flow_started(UNIQUE_ID)

    assert discovery._is_flow_throttled(UNIQUE_ID)


def test_flow_throttle_expires(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test expired discovery flow throttle entries are pruned."""
    discovery = ItachDiscovery(hass)

    current_time = 1000.0

    def fake_monotonic() -> float:
        return current_time

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.time.monotonic",
        fake_monotonic,
    )

    discovery._mark_flow_started(UNIQUE_ID)
    assert discovery._is_flow_throttled(UNIQUE_ID)

    current_time = 1000.0 + FLOW_THROTTLE_SECONDS + 1

    assert not discovery._is_flow_throttled(UNIQUE_ID)
    assert UNIQUE_ID not in discovery._recent_flows


async def test_async_start_listener_failure(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovery start handles listener start failure."""
    listener = MagicMock()
    listener.async_start = AsyncMock(return_value=False)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.ItachDiscoveryListener",
        MagicMock(return_value=listener),
    )

    discovery = ItachDiscovery(hass)
    await discovery.async_start()

    assert discovery._listener is None


async def test_async_start_success_and_idempotent(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovery start creates one listener and is idempotent."""
    listener = MagicMock()
    listener.async_start = AsyncMock(return_value=True)

    listener_factory = MagicMock(return_value=listener)
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.ItachDiscoveryListener",
        listener_factory,
    )

    discovery = ItachDiscovery(hass)

    await discovery.async_start()
    await discovery.async_start()

    assert discovery._listener is listener
    listener_factory.assert_called_once()
    listener.async_start.assert_awaited_once()


async def test_async_stop_cleanup(hass: HomeAssistant) -> None:
    """Test discovery stop stops listener and clears caches."""
    listener = MagicMock()
    listener.async_stop = AsyncMock()
    discovery = ItachDiscovery(hass)
    discovery._listener = listener
    discovery._known_devices[HOST] = UNIQUE_ID
    discovery._recent_flows[UNIQUE_ID] = 1000.0
    discovery._pending_host_updates["entry-id"] = {"host": HOST, "count": 1}

    await discovery.async_stop()

    assert discovery._listener is None
    assert discovery._known_devices == {}
    assert discovery._recent_flows == {}
    assert discovery._pending_host_updates == {}
    listener.async_stop.assert_awaited_once()


async def test_handle_beacon_triggers_flow() -> None:
    """Test handler starts a discovery flow for a valid beacon."""
    hass = MagicMock()
    async_init = AsyncMock(return_value={"type": "form"})
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    hass.config_entries.async_entries = MagicMock(return_value=[])

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    assert discovery.get_known_device_id(HOST) == UNIQUE_ID
    async_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={
            "host": HOST,
            "port": 4998,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )


async def test_handle_beacon_ignores_missing_uuid() -> None:
    """Test handler ignores beacons missing UUID."""
    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid="not-a-device-id", model="iTachIP2IR")
    )

    async_init.assert_not_awaited()


async def test_handle_beacon_ignores_non_ip2ir() -> None:
    """Test handler ignores non-IP2IR Global Caché devices."""
    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2SL")
    )

    async_init.assert_not_awaited()


async def test_handle_beacon_ignores_already_configured_and_updates_host() -> None:
    """Test handler updates host and skips flow for configured device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title=f"iTach IP2IR ({HOST})",
    )

    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    update_entry = MagicMock()
    schedule_reload = MagicMock()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_update_entry",
        update_entry,
    )
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=NEW_HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )
    update_entry.assert_not_called()
    schedule_reload.assert_not_called()

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=NEW_HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    async_init.assert_not_awaited()
    update_entry.assert_called_once_with(
        entry,
        title=f"iTach IP2IR ({NEW_HOST})",
        data={
            "host": NEW_HOST,
            "port": 4998,
        },
    )
    schedule_reload.assert_called_once_with(entry.entry_id)


async def test_handle_beacon_throttled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handler skips recently started discovery flows."""
    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    hass.config_entries.async_entries = MagicMock(return_value=[])

    discovery = ItachDiscovery(hass)
    monkeypatch.setattr(discovery, "_is_flow_throttled", lambda unique_id: True)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    async_init.assert_not_awaited()


async def test_handle_beacon_flow_start_exception_is_handled() -> None:
    """Test handler handles discovery flow startup exceptions."""
    hass = MagicMock()
    async_init = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    hass.config_entries.async_entries = MagicMock(return_value=[])

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    async_init.assert_awaited_once()


async def test_pyitach_listener_receives_beacon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test hardware listener dispatches parsed beacons."""
    fake_socket = FakeSocket()
    received: list[ItachDiscoveryBeacon] = []

    async def on_beacon(beacon: ItachDiscoveryBeacon) -> None:
        received.append(beacon)
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "sock_recvfrom",
        AsyncMock(return_value=(_beacon().encode(), (HOST, DISCOVERY_PORT))),
    )

    listener = ItachDiscoveryListener(on_beacon)
    assert await listener.async_start()

    assert listener._task is not None
    with pytest.raises(asyncio.CancelledError):
        await listener._task

    assert received == [
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    ]
    await listener.async_stop()


async def test_pyitach_listener_socket_oserror_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test hardware listener continues after socket OSError."""
    fake_socket = FakeSocket()
    on_beacon = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "sock_recvfrom",
        AsyncMock(
            side_effect=[
                OSError("socket failed"),
                asyncio.CancelledError,
            ],
        ),
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.asyncio.sleep",
        AsyncMock(),
    )

    listener = ItachDiscoveryListener(on_beacon)
    assert await listener.async_start()

    assert listener._task is not None
    with pytest.raises(asyncio.CancelledError):
        await listener._task

    on_beacon.assert_not_awaited()
    await listener.async_stop()


def test_normalize_host_and_uuid_none_values() -> None:
    """Test normalization helpers handle missing values."""
    assert _normalize_host(None) is None
    assert _normalize_uuid(None) is None


def test_normalize_host_blank_value() -> None:
    """Test blank host normalizes to None."""
    assert _normalize_host("   .") is None


def test_normalize_uuid_rejects_invalid_and_zero_values() -> None:
    """Test UUID normalization rejects invalid and all-zero IDs."""
    assert _normalize_uuid("not-a-device-id") is None
    assert _normalize_uuid("000000000000") is None


async def test_pyitach_async_discover_once_immediate_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test one-shot discovery returns None when deadline already elapsed."""
    fake_socket = FakeSocket()
    loop = asyncio.get_running_loop()
    recv = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.pyitach._discovery.socket.socket",
        lambda *args, **kwargs: fake_socket,
    )
    monkeypatch.setattr(loop, "sock_recvfrom", recv)

    assert await pyitach_async_discover_once(timeout=0.0) is None
    recv.assert_not_awaited()
    assert fake_socket.closed


async def test_async_wait_for_device_id_returns_none_for_blank_host() -> None:
    """Test waiting for a blank host returns None without discovery."""
    assert await async_wait_for_device_id("   ") is None


async def test_async_wait_for_device_id_uses_discovery_cache(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test waiting for device ID uses the permanent discovery cache first."""
    discovery = ItachDiscovery(hass)
    discovery._known_devices[HOST] = UNIQUE_ID
    discover_once = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        discover_once,
    )

    assert (
        await async_wait_for_device_id(HOST, timeout=10.0, discovery=discovery)
        == UNIQUE_ID
    )
    discover_once.assert_not_awaited()


def test_known_device_id_blank_host_returns_none(hass: HomeAssistant) -> None:
    """Test known device lookup handles blank host."""
    discovery = ItachDiscovery(hass)

    assert discovery.get_known_device_id("   ") is None


def test_configured_entry_invalid_unique_id_returns_none(hass: HomeAssistant) -> None:
    """Test configured entry lookup rejects invalid unique IDs."""
    discovery = ItachDiscovery(hass)

    assert discovery._configured_entry("not-a-valid-id") is None


def test_configured_device_host_update_blank_host_noops(hass: HomeAssistant) -> None:
    """Test discovery host update ignores blank discovered host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title=f"iTach IP2IR ({HOST})",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, "   ")

    assert entry.data["host"] == HOST
    schedule_reload.assert_not_called()


def test_parse_beacon_config_url_supports_path_port_and_trailing_slash() -> None:
    """Test Config-URL parsing handles realistic URL variants."""
    message = (
        "AMXB<-SDKClass=Utility>"
        "<-Make=GlobalCache>"
        "<-Model=iTachIP2IR>"
        f"<-UUID={UNIQUE_ID}>"
        f"<-Config-URL=http://{HOST}:80/config/>"
    )

    parsed = _parse_beacon(message, OTHER_HOST)

    assert parsed == ItachDiscoveryBeacon(
        host=HOST,
        uuid=UNIQUE_ID,
        model="iTachIP2IR",
    )


def test_parse_beacon_config_url_rejects_non_http_scheme() -> None:
    """Test Config-URL parsing rejects unsupported URL schemes."""
    message = (
        "AMXB<-SDKClass=Utility>"
        "<-Make=GlobalCache>"
        "<-Model=iTachIP2IR>"
        f"<-UUID={UNIQUE_ID}>"
        f"<-Config-URL=ftp://{HOST}/config>"
    )

    assert _parse_beacon(message, OTHER_HOST) is None


def test_parse_beacon_config_url_malformed_ipv6_falls_back_to_packet_host() -> None:
    """Test malformed Config-URL falls back to the packet source host."""
    message = (
        "AMXB<-SDKClass=Utility>"
        "<-Make=GlobalCache>"
        "<-Model=iTachIP2IR>"
        f"<-UUID={UNIQUE_ID}>"
        "<-Config-URL=http://[bad>"
    )

    assert _parse_beacon(message, OTHER_HOST) == ItachDiscoveryBeacon(
        host=OTHER_HOST,
        uuid=UNIQUE_ID,
        model="iTachIP2IR",
    )
