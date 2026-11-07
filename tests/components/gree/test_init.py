"""Tests for Gree setup and shared discovery."""

import asyncio
from collections.abc import Callable, Generator
from datetime import timedelta
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from greeclimate.device import DeviceInfo
from greeclimate.discovery import Discovery as RealDiscovery
from greeclimate.network import Response
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.gree.const import (
    DISCOVERY_SCAN_INTERVAL,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)
from homeassistant.components.gree.discovery import (
    async_get_discovery,
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import async_setup_gree, build_device_mock


@pytest.fixture(autouse=True)
def mock_broadcast_addresses() -> Generator[AsyncMock]:
    """Keep background discovery independent of the host's network interfaces."""
    with patch(
        "homeassistant.components.gree.discovery.async_get_ipv4_broadcast_addresses",
        return_value={IPv4Address("192.0.2.255")},
    ) as broadcasts:
        yield broadcasts


async def test_independent_entries(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """Unloading and reloading one entry leaves the other connection intact."""
    first_device = device()
    second_device = build_device_mock(
        name="fake-device-2", ipAddress="1.1.1.2", identifier="aabbcc112244"
    )
    discovery.mock_devices.clear()
    device.side_effect = lambda info: {
        first_device.device_info.mac: first_device,
        second_device.device_info.mac: second_device,
    }[info.mac]
    first = await async_setup_gree(hass, first_device)
    second = await async_setup_gree(hass, second_device)
    assert first.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    assert first.runtime_data is not second.runtime_data
    assert first.runtime_data.device is first_device
    assert second.runtime_data.device is second_device
    second_coordinator = second.runtime_data
    second_state = hass.states.get("climate.fake_device_2")
    assert second_state is not None

    await hass.config_entries.async_unload(first.entry_id)
    assert first.state is ConfigEntryState.NOT_LOADED
    first_device.close.assert_called_once()
    second_device.close.assert_not_called()
    assert second.runtime_data is second_coordinator
    assert hass.states.get("climate.fake_device_2") == second_state
    await second_coordinator.push_state_update()
    second_device.push_state_update.assert_awaited_once()

    replacement = build_device_mock()
    device.side_effect = lambda info: {
        replacement.device_info.mac: replacement,
        second_device.device_info.mac: second_device,
    }[info.mac]
    await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    assert first.state is ConfigEntryState.LOADED
    assert first.runtime_data.device is replacement
    assert second.runtime_data is second_coordinator
    second_device.close.assert_not_called()


async def test_background_discovery_requires_confirmation(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Background observations offer one confirmation without creating entities."""
    await hass.async_start()
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "discovery_confirm"
    assert flows[0]["context"]["unique_id"] == device().device_info.mac
    assert not hass.config_entries.async_entries(DOMAIN)
    assert not device_registry.devices
    assert not entity_registry.entities
    device().bind.assert_not_awaited()

    freezer.tick(timedelta(seconds=DISCOVERY_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.config_entries.flow.async_progress()) == 1
    assert not hass.config_entries.async_entries(DOMAIN)
    assert all(instance.closed for instance in discovery.instances)
    device().bind.assert_not_awaited()


async def test_empty_legacy_entry_retained_without_connection(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """An empty legacy entry stays loaded without attempting device setup."""
    discovery.mock_devices.clear()
    entry = MockConfigEntry(domain=DOMAIN, version=1, unique_id="gree")
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert entry.version == 1
    assert entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert not hass.states.async_all("climate")
    device().bind.assert_not_awaited()
    device().update_state.assert_not_awaited()


async def test_hostless_entry_retries_without_connection(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """An offline migrated unit is retained without publishing invented state."""
    discovery.mock_devices.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=device().device_info.mac,
        data={**device_info_to_data(device().device_info), "host": None},
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    device().bind.assert_not_awaited()
    assert not hass.states.async_all("climate")


async def test_scan_empty_targets(hass: HomeAssistant, discovery: MagicMock) -> None:
    """No selected interfaces never falls back to library-wide broadcasting."""
    with patch(
        "homeassistant.components.gree.discovery.async_get_ipv4_broadcast_addresses",
        return_value=set(),
    ):
        result = await async_get_discovery(hass).async_scan()
    assert result == {}
    discovery.instances[0].scan.assert_not_awaited()
    assert discovery.instances[0].closed


async def test_scan_enumerates_broadcast_addresses(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """A broadcast scan uses only Home Assistant's configured interfaces."""
    addresses = {IPv4Address("192.0.2.255")}
    with patch(
        "homeassistant.components.gree.discovery.async_get_ipv4_broadcast_addresses",
        return_value=addresses,
    ) as broadcasts:
        await async_get_discovery(hass).async_scan()
    broadcasts.assert_awaited_once_with(hass)
    discovery.instances[0].scan.assert_awaited_once_with(
        wait_for=DISCOVERY_TIMEOUT, target_addresses=list(addresses)
    )


async def test_scans_are_fresh(hass: HomeAssistant, discovery: MagicMock) -> None:
    """An earlier observation is not evidence of a response to the next scan."""
    scanner = async_get_discovery(hass)
    assert await scanner.async_scan()
    discovery.mock_devices.clear()
    assert await scanner.async_scan() == {}
    assert all(instance.closed for instance in discovery.instances)


async def test_concurrent_scans_serialize(
    hass: HomeAssistant, discovery: MagicMock, device: MagicMock
) -> None:
    """Concurrent consumers cannot overlap their discovery transports."""
    started = asyncio.Event()
    release = asyncio.Event()
    queued = asyncio.Event()
    info = device().device_info

    async def first_scan(**kwargs: object) -> list[DeviceInfo]:
        started.set()
        await release.wait()
        return [info]

    first_discovery = Mock(scan=AsyncMock(side_effect=first_scan), close=Mock())
    second_discovery = Mock(scan=AsyncMock(return_value=[]), close=Mock())
    discovery.side_effect = [first_discovery, second_discovery]
    scanner = async_get_discovery(hass)
    first = asyncio.create_task(scanner.async_scan())
    await started.wait()

    async def queued_scan() -> dict[str, DeviceInfo]:
        queued.set()
        return await scanner.async_scan()

    second = asyncio.create_task(queued_scan())
    await queued.wait()
    second_discovery.scan.assert_not_awaited()
    release.set()
    assert await first == {normalize_identifier(info.mac): info}
    assert await second == {}
    first_discovery.close.assert_called_once()
    second_discovery.close.assert_called_once()


@pytest.mark.parametrize("error", [OSError("network down"), TimeoutError()])
async def test_scan_error_releases_transport_and_lock(
    hass: HomeAssistant, discovery: MagicMock, error: Exception
) -> None:
    """Network failures propagate and do not block the following scan."""
    failed = Mock(scan=AsyncMock(side_effect=error), close=Mock())
    following = Mock(scan=AsyncMock(return_value=[]), close=Mock())
    discovery.side_effect = [failed, following]
    scanner = async_get_discovery(hass)
    with pytest.raises(type(error)):
        await scanner.async_scan()
    assert await scanner.async_scan() == {}
    failed.close.assert_called_once()
    following.close.assert_called_once()


async def test_scan_cancellation_releases_transport_and_lock(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Cancelling an interactive scan permits another consumer to scan."""
    started = asyncio.Event()

    async def blocked_scan(**kwargs: object) -> list[DeviceInfo]:
        started.set()
        await asyncio.Event().wait()
        return []

    cancelled = Mock(scan=AsyncMock(side_effect=blocked_scan), close=Mock())
    following = Mock(scan=AsyncMock(return_value=[]), close=Mock())
    discovery.side_effect = [cancelled, following]
    scanner = async_get_discovery(hass)
    task = asyncio.create_task(scanner.async_scan())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await scanner.async_scan() == {}
    cancelled.close.assert_called_once()
    following.close.assert_called_once()


async def test_stop_discards_late_scan_results(
    hass: HomeAssistant, discovery: MagicMock, device: MagicMock
) -> None:
    """Stop closes active discovery and neither late nor queued work survives."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_scan(**kwargs: object) -> list[DeviceInfo]:
        started.set()
        await release.wait()
        return [device().device_info]

    active = Mock(scan=AsyncMock(side_effect=delayed_scan), close=Mock())
    discovery.side_effect = [active]
    scanner = async_get_discovery(hass)
    task = asyncio.create_task(scanner.async_scan())
    await started.wait()
    scanner.async_stop()
    scanner.async_stop()
    active.close.assert_called_once()
    release.set()
    assert await task == {}
    assert await scanner.async_scan() == {}
    assert not hass.config_entries.flow.async_progress()


async def test_stop_during_endpoint_creation_closes_late_transport(
    hass: HomeAssistant,
    discovery: MagicMock,
    device: MagicMock,
) -> None:
    """A delayed library connection cannot reopen scanning after stop."""
    started = asyncio.Event()
    release = asyncio.Event()
    active = RealDiscovery(DISCOVERY_TIMEOUT)
    discovery.side_effect = [active]
    transport = MagicMock(spec=asyncio.DatagramTransport)
    transport.is_closing.return_value = False
    info = device().device_info

    def close_transport() -> None:
        transport.is_closing.return_value = True
        active.connection_lost(None)

    transport.close.side_effect = close_transport

    async def delayed_endpoint(
        protocol_factory: Callable[[], RealDiscovery], **kwargs: object
    ) -> tuple[asyncio.DatagramTransport, RealDiscovery]:
        started.set()
        await release.wait()
        protocol = protocol_factory()
        protocol.connection_made(transport)
        assert not transport.is_closing()
        await protocol.device_found(info)
        return transport, protocol

    async def scan_without_response_delay(
        *, wait_for: int, target_addresses: list[IPv4Address]
    ) -> list[DeviceInfo]:
        return await RealDiscovery.scan(
            active, wait_for=0, target_addresses=target_addresses
        )

    await hass.async_start()
    with (
        patch.object(active, "scan", side_effect=scan_without_response_delay),
        patch.object(
            asyncio.get_running_loop(),
            "create_datagram_endpoint",
            side_effect=delayed_endpoint,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await started.wait()
        scanner = async_get_discovery(hass)
        scanner.async_stop()
        transport.close.assert_not_called()
        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        transport.close.assert_called_once()

    assert active.devices == [info]
    assert transport.is_closing()
    assert await scanner.async_scan() == {}
    assert not hass.config_entries.flow.async_progress()
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_background_scan_network_error_retries(
    hass: HomeAssistant,
    discovery: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed background scan logs a warning, not a successful empty result."""
    await hass.async_start()
    with patch(
        "homeassistant.components.gree.discovery.async_get_ipv4_broadcast_addresses",
        side_effect=OSError("network down"),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)
    assert "Unable to discover Gree devices" in caplog.text
    assert not hass.config_entries.flow.async_progress()
    assert all(instance.closed for instance in discovery.instances)
    freezer.tick(timedelta(seconds=DISCOVERY_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.config_entries.flow.async_progress()) == 1
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_background_scan_cannot_create_flows_after_stop(
    hass: HomeAssistant, discovery: MagicMock, device: MagicMock
) -> None:
    """Even a late scan completion cannot offer devices during shutdown."""
    started = asyncio.Event()

    async def late_scan(**kwargs: object) -> list[DeviceInfo]:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return [device().device_info]
        return []

    active = Mock(scan=AsyncMock(side_effect=late_scan), close=Mock())
    discovery.side_effect = [active]
    await hass.async_start()
    assert await async_setup_component(hass, DOMAIN, {})
    await started.wait()
    await hass.async_stop()
    active.close.assert_called()
    assert not hass.config_entries.flow.async_progress()
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_ha_stop_closes_devices_and_scanner(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """HA stop closes the session and forbids new discovery work."""
    await hass.async_start()
    entry = await async_setup_gree(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    scanner = async_get_discovery(hass)
    await hass.async_stop()
    device().close.assert_called_once()
    count = len(discovery.instances)
    assert await scanner.async_scan() == {}
    assert len(discovery.instances) == count
    data = entry.runtime_data.data
    device().emit_response(Response.RESULT)
    assert entry.runtime_data.data is data


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AA:BB-CC.DD", "aabbccdd"),
        ("LongerReportedIdentity", "longerreportedidentity"),
    ],
)
def test_normalize_identifier(raw: str, expected: str) -> None:
    """Identifier comparison accepts the library's variable-length identifiers."""
    assert normalize_identifier(raw) == expected


@pytest.mark.parametrize("raw", [None, 123, "", ":-."])
def test_normalize_identifier_rejects_invalid_identifier(raw: str | int | None) -> None:
    """An unusable migration identifier cannot silently acquire ownership."""
    with pytest.raises(ValueError, match="nonempty string"):
        normalize_identifier(raw)  # type: ignore[arg-type]
