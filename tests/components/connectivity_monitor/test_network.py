"""Tests for the NetworkProbe helpers of Connectivity Monitor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.connectivity_monitor.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    DEFAULT_DNS_SERVER,
    PROTOCOL_AD_DC,
    PROTOCOL_ICMP,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
)
from homeassistant.components.connectivity_monitor.network import NetworkProbe
from homeassistant.core import HomeAssistant

# ──────────────────────────────────────────────────────────────────────────────
# Helpers / setup
# ──────────────────────────────────────────────────────────────────────────────


def _make_probe(
    hass: HomeAssistant, dns_server: str = DEFAULT_DNS_SERVER
) -> NetworkProbe:
    return NetworkProbe(hass, dns_server)


# ──────────────────────────────────────────────────────────────────────────────
# async_update_target — TCP
# ──────────────────────────────────────────────────────────────────────────────


async def test_update_target_tcp_success(hass: HomeAssistant) -> None:
    """Returns connected=True and a latency value for a successful TCP probe."""
    probe = _make_probe(hass)

    with (
        patch.object(
            probe,
            "_resolve_host",
            new=AsyncMock(return_value="192.168.1.1"),
        ),
        patch.object(
            probe,
            "_get_mac_address",
            new=AsyncMock(return_value="AA:BB:CC:DD:EE:FF"),
        ),
        patch.object(
            probe,
            "_async_test_tcp",
            new=AsyncMock(return_value=5.2),
        ),
    ):
        result = await probe.async_update_target(
            {CONF_HOST: "192.168.1.1", CONF_PROTOCOL: PROTOCOL_TCP, CONF_PORT: 80}
        )

    assert result["connected"] is True
    assert result["latency"] == 5.2
    assert result["resolved_ip"] == "192.168.1.1"
    assert result["mac_address"] == "AA:BB:CC:DD:EE:FF"


async def test_update_target_tcp_failure(hass: HomeAssistant) -> None:
    """Returns connected=False when TCP probe returns None."""
    probe = _make_probe(hass)

    with (
        patch.object(probe, "_resolve_host", new=AsyncMock(return_value="10.0.0.1")),
        patch.object(probe, "_get_mac_address", new=AsyncMock(return_value=None)),
        patch.object(probe, "_async_test_tcp", new=AsyncMock(return_value=None)),
    ):
        result = await probe.async_update_target(
            {CONF_HOST: "10.0.0.1", CONF_PROTOCOL: PROTOCOL_TCP, CONF_PORT: 443}
        )

    assert result["connected"] is False
    assert result["latency"] is None


async def test_update_target_unresolvable_host(hass: HomeAssistant) -> None:
    """Returns connected=False when host cannot be resolved."""
    probe = _make_probe(hass)

    with patch.object(probe, "_resolve_host", new=AsyncMock(return_value=None)):
        result = await probe.async_update_target(
            {
                CONF_HOST: "unresolvable.local",
                CONF_PROTOCOL: PROTOCOL_TCP,
                CONF_PORT: 80,
            }
        )

    assert result["connected"] is False
    assert result["resolved_ip"] is None


async def test_update_target_ad_dc_uses_tcp(hass: HomeAssistant) -> None:
    """AD_DC protocol routes to _async_test_tcp."""
    probe = _make_probe(hass)

    with (
        patch.object(probe, "_resolve_host", new=AsyncMock(return_value="10.0.0.2")),
        patch.object(probe, "_get_mac_address", new=AsyncMock(return_value=None)),
        patch.object(
            probe, "_async_test_tcp", new=AsyncMock(return_value=10.0)
        ) as mock_tcp,
        patch.object(
            probe, "_async_test_udp", new=AsyncMock(return_value=None)
        ) as mock_udp,
    ):
        result = await probe.async_update_target(
            {CONF_HOST: "10.0.0.2", CONF_PROTOCOL: PROTOCOL_AD_DC, CONF_PORT: 389}
        )

    mock_tcp.assert_awaited_once()
    mock_udp.assert_not_awaited()
    assert result["connected"] is True


async def test_update_target_udp_success(hass: HomeAssistant) -> None:
    """Returns connected=True for a successful UDP probe."""
    probe = _make_probe(hass)

    with (
        patch.object(probe, "_resolve_host", new=AsyncMock(return_value="10.0.0.3")),
        patch.object(probe, "_get_mac_address", new=AsyncMock(return_value=None)),
        patch.object(probe, "_async_test_udp", new=AsyncMock(return_value=3.7)),
    ):
        result = await probe.async_update_target(
            {CONF_HOST: "10.0.0.3", CONF_PROTOCOL: PROTOCOL_UDP, CONF_PORT: 53}
        )

    assert result["connected"] is True
    assert result["latency"] == 3.7


async def test_update_target_icmp(hass: HomeAssistant) -> None:
    """Routes ICMP to _async_icmp_ping."""
    probe = _make_probe(hass)

    with (
        patch.object(probe, "_resolve_host", new=AsyncMock(return_value="10.0.0.4")),
        patch.object(probe, "_get_mac_address", new=AsyncMock(return_value=None)),
        patch.object(
            probe, "_async_icmp_ping", new=AsyncMock(return_value=1.0)
        ) as mock_ping,
    ):
        result = await probe.async_update_target(
            {CONF_HOST: "10.0.0.4", CONF_PROTOCOL: PROTOCOL_ICMP}
        )

    mock_ping.assert_awaited_once()
    assert result["connected"] is True


async def test_update_target_oserror(hass: HomeAssistant) -> None:
    """Returns connected=False when an OSError is raised."""
    probe = _make_probe(hass)

    with (
        patch.object(probe, "_resolve_host", new=AsyncMock(return_value="10.0.0.5")),
        patch.object(probe, "_get_mac_address", new=AsyncMock(return_value=None)),
        patch.object(
            probe, "_async_test_tcp", new=AsyncMock(side_effect=OSError("refused"))
        ),
    ):
        result = await probe.async_update_target(
            {CONF_HOST: "10.0.0.5", CONF_PROTOCOL: PROTOCOL_TCP, CONF_PORT: 80}
        )

    assert result["connected"] is False


# ──────────────────────────────────────────────────────────────────────────────
# _async_test_tcp
# ──────────────────────────────────────────────────────────────────────────────


async def test_async_test_tcp_success(hass: HomeAssistant) -> None:
    """Returns latency when TCP connection succeeds."""
    probe = _make_probe(hass)

    mock_writer = AsyncMock()
    mock_writer.wait_closed = AsyncMock()

    with patch(
        "homeassistant.components.connectivity_monitor.network.asyncio.open_connection",
        return_value=(AsyncMock(), mock_writer),
    ):
        latency = await probe._async_test_tcp("127.0.0.1", 80)

    assert latency is not None
    assert latency >= 0


async def test_async_test_tcp_oserror(hass: HomeAssistant) -> None:
    """Returns None when TCP connection fails with OSError."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.asyncio.open_connection",
        side_effect=OSError("connection refused"),
    ):
        latency = await probe._async_test_tcp("10.0.0.1", 9999)

    assert latency is None


async def test_async_test_tcp_timeout(hass: HomeAssistant) -> None:
    """Returns None when TCP connection times out."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.asyncio.wait_for",
        side_effect=TimeoutError(),
    ):
        latency = await probe._async_test_tcp("10.0.0.1", 80)

    assert latency is None


# ──────────────────────────────────────────────────────────────────────────────
# _async_test_udp
# ──────────────────────────────────────────────────────────────────────────────


async def test_async_test_udp_success(hass: HomeAssistant) -> None:
    """Returns latency when UDP socket connect succeeds."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.socket.socket"
    ) as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        hass.async_add_executor_job = AsyncMock(return_value=None)

        latency = await probe._async_test_udp("10.0.0.1", 53)

    assert latency is not None
    assert latency >= 0


async def test_async_test_udp_oserror(hass: HomeAssistant) -> None:
    """Returns None when UDP connect raises OSError."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.socket.socket"
    ) as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        hass.async_add_executor_job = AsyncMock(side_effect=OSError("unreachable"))

        latency = await probe._async_test_udp("10.0.0.1", 53)

    assert latency is None


# ──────────────────────────────────────────────────────────────────────────────
# _async_icmp_ping
# ──────────────────────────────────────────────────────────────────────────────


async def test_async_icmp_ping_import_error(hass: HomeAssistant) -> None:
    """Returns None when icmplib is not installed."""
    probe = _make_probe(hass)

    with patch(
        "builtins.__import__",
        side_effect=ImportError("No module named 'icmplib'"),
    ):
        result = await probe._async_icmp_ping("host", "10.0.0.1")

    assert result is None


async def test_async_icmp_ping_success(hass: HomeAssistant) -> None:
    """Returns avg_rtt when ping succeeds."""
    probe = _make_probe(hass)

    mock_response = MagicMock()
    mock_response.is_alive = True
    mock_response.avg_rtt = 12.5

    with patch(
        "homeassistant.components.connectivity_monitor.network.NetworkProbe._async_icmp_ping",
        new=AsyncMock(return_value=12.5),
    ):
        result = await probe._async_icmp_ping("host", "10.0.0.1")

    assert result == 12.5


async def test_async_icmp_ping_not_alive(hass: HomeAssistant) -> None:
    """Returns None when ping response shows host not alive."""
    probe = _make_probe(hass)

    mock_response = MagicMock()
    mock_response.is_alive = False
    mock_response.avg_rtt = None

    mock_icmplib = MagicMock()
    mock_icmplib.SocketPermissionError = OSError
    mock_icmplib.NameLookupError = OSError
    mock_icmplib.async_ping = AsyncMock(return_value=mock_response)

    with patch.dict("sys.modules", {"icmplib": mock_icmplib}):
        result = await probe._async_icmp_ping("host", "10.0.0.1")

    assert result is None


async def test_async_icmp_ping_socket_permission_retry(hass: HomeAssistant) -> None:
    """Retries unprivileged when privileged mode raises SocketPermissionError."""
    probe = _make_probe(hass)

    mock_response = MagicMock()
    mock_response.is_alive = True
    mock_response.avg_rtt = 8.0

    class FakeSocketPermissionError(Exception):
        pass

    async def fake_ping(ip, count, timeout, privileged):
        if privileged:
            raise FakeSocketPermissionError
        return mock_response

    mock_icmplib = MagicMock()
    mock_icmplib.SocketPermissionError = FakeSocketPermissionError
    mock_icmplib.NameLookupError = Exception
    mock_icmplib.async_ping = fake_ping

    with patch.dict("sys.modules", {"icmplib": mock_icmplib}):
        result = await probe._async_icmp_ping("host", "10.0.0.1")

    assert result == 8.0
    assert probe._icmp_privileged.get("host") is False


async def test_async_icmp_ping_name_lookup_error(hass: HomeAssistant) -> None:
    """Returns None on NameLookupError."""
    probe = _make_probe(hass)

    class FakeNameLookupError(Exception):
        pass

    mock_icmplib = MagicMock()
    mock_icmplib.SocketPermissionError = Exception
    mock_icmplib.NameLookupError = FakeNameLookupError
    mock_icmplib.async_ping = AsyncMock(side_effect=FakeNameLookupError())

    with patch.dict("sys.modules", {"icmplib": mock_icmplib}):
        result = await probe._async_icmp_ping("host", "badhost")

    assert result is None


async def test_async_icmp_ping_oserror(hass: HomeAssistant) -> None:
    """Returns None on OSError from icmplib."""
    probe = _make_probe(hass)

    mock_icmplib = MagicMock()
    mock_icmplib.SocketPermissionError = PermissionError
    mock_icmplib.NameLookupError = OSError
    mock_icmplib.async_ping = AsyncMock(side_effect=RuntimeError("ping failed"))

    with patch.dict("sys.modules", {"icmplib": mock_icmplib}):
        result = await probe._async_icmp_ping("host", "10.0.0.1")

    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# _get_mac_address
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_mac_address_found(hass: HomeAssistant) -> None:
    """Returns MAC address parsed from ARP output."""
    probe = _make_probe(hass)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b"? (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether]", b"")
    )

    with patch(
        "homeassistant.components.connectivity_monitor.network.asyncio.create_subprocess_shell",
        return_value=mock_proc,
    ):
        mac = await probe._get_mac_address("192.168.1.1")

    assert mac == "AA:BB:CC:DD:EE:FF"


async def test_get_mac_address_not_found(hass: HomeAssistant) -> None:
    """Returns None when ARP output has no MAC address pattern."""
    probe = _make_probe(hass)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"192.168.1.1 -- no entry", b""))

    with patch(
        "homeassistant.components.connectivity_monitor.network.asyncio.create_subprocess_shell",
        return_value=mock_proc,
    ):
        mac = await probe._get_mac_address("192.168.1.1")

    assert mac is None


async def test_get_mac_address_oserror(hass: HomeAssistant) -> None:
    """Returns None on OSError."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.asyncio.create_subprocess_shell",
        side_effect=OSError("subprocess failed"),
    ):
        mac = await probe._get_mac_address("192.168.1.1")

    assert mac is None


# ──────────────────────────────────────────────────────────────────────────────
# _resolve_host
# ──────────────────────────────────────────────────────────────────────────────


async def test_resolve_host_ipv4_passthrough(hass: HomeAssistant) -> None:
    """IPv4 addresses are returned as-is without DNS lookup."""
    probe = _make_probe(hass)
    result = await probe._resolve_host("192.168.1.100")
    assert result == "192.168.1.100"


async def test_resolve_host_ipv6_passthrough(hass: HomeAssistant) -> None:
    """IPv6 addresses are returned as-is without DNS lookup."""
    probe = _make_probe(hass)
    result = await probe._resolve_host("::1")
    assert result == "::1"


async def test_resolve_host_no_dns_resolver(hass: HomeAssistant) -> None:
    """Returns None when dns module is unavailable."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.HAVE_DNS",
        False,
    ):
        result = await probe._resolve_host("example.com")

    assert result is None


async def test_resolve_host_with_dns(hass: HomeAssistant) -> None:
    """Returns resolved IP when DNS lookup succeeds."""
    probe = _make_probe(hass)

    mock_answer = MagicMock()
    mock_answer.__str__ = lambda self: "93.184.216.34"

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [mock_answer]

    with (
        patch(
            "homeassistant.components.connectivity_monitor.network.HAVE_DNS",
            True,
        ),
        patch.object(probe, "_get_resolver", new=AsyncMock(return_value=mock_resolver)),
    ):
        result = await probe._resolve_host("example.com")

    assert result == "93.184.216.34"


async def test_resolve_host_dns_resolution_fails(hass: HomeAssistant) -> None:
    """Returns None when DNS resolver raises."""
    probe = _make_probe(hass)

    mock_resolver = MagicMock()
    mock_resolver.resolve.side_effect = Exception("SERVFAIL")

    with (
        patch(
            "homeassistant.components.connectivity_monitor.network.HAVE_DNS",
            True,
        ),
        patch.object(probe, "_get_resolver", new=AsyncMock(return_value=mock_resolver)),
    ):
        result = await probe._resolve_host("bad.example.com")

    assert result is None


async def test_resolve_host_oserror(hass: HomeAssistant) -> None:
    """Returns None on unexpected OSError."""
    probe = _make_probe(hass)

    with patch.object(
        probe, "_get_resolver", new=AsyncMock(side_effect=OSError("unexpected"))
    ):
        result = await probe._resolve_host("host.example.com")

    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# _get_resolver
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_resolver_creates_resolver(hass: HomeAssistant) -> None:
    """Creates and caches a DNS Resolver on first call."""
    probe = _make_probe(hass)

    mock_resolver = MagicMock()

    with (
        patch(
            "homeassistant.components.connectivity_monitor.network.HAVE_DNS",
            True,
        ),
        patch(
            "homeassistant.components.connectivity_monitor.network.dns_resolver",
        ) as mock_dns,
    ):
        mock_dns.Resolver.return_value = mock_resolver
        hass.async_add_executor_job = AsyncMock(return_value=mock_resolver)

        resolver = await probe._get_resolver()

    assert resolver is mock_resolver
    assert probe._resolver is mock_resolver


async def test_get_resolver_returns_cached(hass: HomeAssistant) -> None:
    """Returns cached resolver on subsequent calls without creating a new one."""
    probe = _make_probe(hass)
    mock_resolver = MagicMock()
    probe._resolver = mock_resolver

    with patch(
        "homeassistant.components.connectivity_monitor.network.HAVE_DNS",
        True,
    ):
        resolver = await probe._get_resolver()

    assert resolver is mock_resolver


async def test_get_resolver_no_dns(hass: HomeAssistant) -> None:
    """Returns None when dns is not available."""
    probe = _make_probe(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.network.HAVE_DNS",
        False,
    ):
        resolver = await probe._get_resolver()

    assert resolver is None


# ──────────────────────────────────────────────────────────────────────────────
# async_prepare_host
# ──────────────────────────────────────────────────────────────────────────────


async def test_async_prepare_host_caches_resolution(hass: HomeAssistant) -> None:
    """Resolved IP and MAC are cached after first call."""
    probe = _make_probe(hass)

    with (
        patch.object(
            probe, "_resolve_host", new=AsyncMock(return_value="10.0.0.1")
        ) as mock_resolve,
        patch.object(
            probe, "_get_mac_address", new=AsyncMock(return_value="DE:AD:BE:EF:00:01")
        ) as mock_mac,
    ):
        await probe.async_prepare_host("myhost")
        await probe.async_prepare_host("myhost")  # second call should use cache

    # resolve and get_mac should each be called only once
    mock_resolve.assert_awaited_once_with("myhost")
    mock_mac.assert_awaited_once_with("10.0.0.1")


async def test_async_prepare_host_unresolvable(hass: HomeAssistant) -> None:
    """When host is unresolvable, MAC lookup is skipped."""
    probe = _make_probe(hass)

    with (
        patch.object(probe, "_resolve_host", new=AsyncMock(return_value=None)),
        patch.object(
            probe, "_get_mac_address", new=AsyncMock(return_value=None)
        ) as mock_mac,
    ):
        await probe.async_prepare_host("unresolvable.local")

    mock_mac.assert_not_awaited()
