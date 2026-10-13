"""Tests for Refoss discovery scans."""

from collections.abc import AsyncGenerator
from ipaddress import IPv4Address
from time import monotonic
from unittest.mock import AsyncMock, patch

import pytest
from refoss_ha.exceptions import DeviceTimeoutError

from homeassistant.components.refoss.const import (
    CONF_NETWORKS,
    DISCOVERY_SERVER,
    DOMAIN,
    MAX_ERRORS,
    SWEEP_COOLDOWN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FakeDiscovery, build_base_device_mock, build_device_mock

from tests.common import MockConfigEntry


@pytest.fixture
def fake_discovery() -> FakeDiscovery:
    """Return the discovery double used by setup."""
    return FakeDiscovery()


@pytest.fixture
def configured_networks(request: pytest.FixtureRequest) -> list[str]:
    """Return the networks stored on the test config entry."""
    return getattr(request, "param", ["192.168.20.0/24"])


@pytest.fixture
async def refoss_entry(
    hass: HomeAssistant,
    fake_discovery: FakeDiscovery,
    configured_networks: list[str],
) -> AsyncGenerator[MockConfigEntry]:
    """Set up Refoss with the configured networks."""
    with (
        patch(
            "homeassistant.components.refoss.util.Discovery",
            return_value=fake_discovery,
        ),
        patch(
            "homeassistant.components.refoss.bridge.async_build_base_device",
            return_value=build_base_device_mock(),
        ),
        patch(
            "homeassistant.components.refoss.bridge.async_get_ipv4_broadcast_addresses",
            new_callable=AsyncMock,
            return_value={
                IPv4Address("255.255.255.255"),
                IPv4Address("10.9.8.255"),
            },
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={CONF_NETWORKS: configured_networks} if configured_networks else {},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry


async def test_startup_scan_sweeps_subnet(
    fake_discovery: FakeDiscovery, refoss_entry: MockConfigEntry
) -> None:
    """Test the first scan includes broadcasts and every host in the subnet."""
    startup = fake_discovery.probes[0]
    assert startup is not None
    assert "255.255.255.255" in startup
    assert "10.9.8.255" in startup
    assert "192.168.20.255" in startup
    assert "192.168.20.1" in startup
    assert "192.168.20.254" in startup
    assert "1.1.1.1" not in startup
    assert refoss_entry.runtime_data.coordinators


async def test_later_scan_uses_known_ip_without_subnet_sweep(
    fake_discovery: FakeDiscovery, refoss_entry: MockConfigEntry
) -> None:
    """Test a follow-up scan keeps the known IP and skips the subnet sweep."""
    await refoss_entry.runtime_data.async_scan()

    steady = fake_discovery.probes[1]
    assert steady is not None
    assert "255.255.255.255" in steady
    assert "10.9.8.255" in steady
    assert "192.168.20.255" in steady
    assert "1.1.1.1" in steady
    assert "192.168.20.1" not in steady


async def test_unavailable_device_does_not_sweep_during_cooldown(
    fake_discovery: FakeDiscovery, refoss_entry: MockConfigEntry
) -> None:
    """Test a failed device does not trigger another sweep inside the cooldown."""
    refoss_entry.runtime_data.coordinators[0]._error_count = MAX_ERRORS

    await refoss_entry.runtime_data.async_scan()

    steady = fake_discovery.probes[1]
    assert steady is not None
    assert "192.168.20.1" not in steady


async def test_sweep_retries_after_cooldown_without_failures(
    fake_discovery: FakeDiscovery, refoss_entry: MockConfigEntry
) -> None:
    """Test a configured subnet is scanned again even when no device has failed."""
    service = refoss_entry.runtime_data
    service._last_sweep = monotonic() - (SWEEP_COOLDOWN + 1)

    await service.async_scan()

    sweep = fake_discovery.probes[1]
    assert sweep is not None
    assert "192.168.20.1" in sweep
    assert "192.168.20.254" in sweep
    assert "1.1.1.1" in sweep


@pytest.mark.parametrize("configured_networks", [["10.1.2.3"]], indirect=True)
async def test_configured_host_is_probed_without_subnet_sweep(
    fake_discovery: FakeDiscovery, refoss_entry: MockConfigEntry
) -> None:
    """Test a single configured address is probed as that host only."""
    startup = fake_discovery.probes[0]
    assert startup is not None
    assert "10.1.2.3" in startup
    assert "10.1.2.1" not in startup
    assert "10.1.2.255" not in startup

    refoss_entry.runtime_data._last_sweep = monotonic() - (SWEEP_COOLDOWN + 1)
    await refoss_entry.runtime_data.async_scan()
    later = fake_discovery.probes[1]
    assert later is not None
    assert "10.1.2.3" in later
    assert "10.1.2.1" not in later


@pytest.mark.parametrize("configured_networks", [[]], indirect=True)
async def test_entry_without_networks_does_not_sweep(
    fake_discovery: FakeDiscovery, refoss_entry: MockConfigEntry
) -> None:
    """Test an existing entry keeps broadcasting without scanning a subnet."""
    startup = fake_discovery.probes[0]
    assert startup is not None
    assert "255.255.255.255" in startup
    assert "10.9.8.255" in startup
    assert "192.168.20.1" not in startup

    refoss_entry.runtime_data._last_sweep = monotonic() - (SWEEP_COOLDOWN + 1)
    await refoss_entry.runtime_data.async_scan()
    later = fake_discovery.probes[1]
    assert later is not None
    assert "192.168.20.1" not in later
    assert "1.1.1.1" in later


async def test_timeout_marks_coordinator_unavailable(
    refoss_entry: MockConfigEntry,
) -> None:
    """Test consecutive timeouts increment the coordinator error count."""
    coordinator = refoss_entry.runtime_data.coordinators[0]
    coordinator.device.async_handle_update.side_effect = DeviceTimeoutError

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator._error_count == 1

    await coordinator.async_refresh()

    assert coordinator._error_count == MAX_ERRORS


async def test_options_change_scans_without_reload(
    hass: HomeAssistant,
    fake_discovery: FakeDiscovery,
    refoss_entry: MockConfigEntry,
) -> None:
    """Test saving options probes the new networks without reloading the entry."""
    result = await hass.config_entries.options.async_init(refoss_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_NETWORKS: "10.8.0.0/24"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert refoss_entry.state is ConfigEntryState.LOADED
    assert refoss_entry.options == {CONF_NETWORKS: ["10.8.0.0/24"]}
    latest = fake_discovery.probes[-1]
    assert latest is not None
    assert "10.8.0.255" in latest
    assert "10.8.0.1" in latest


async def test_options_flow_keeps_old_networks_when_scan_fails(
    hass: HomeAssistant, refoss_entry: MockConfigEntry
) -> None:
    """Test a failed options scan does not persist the new networks."""
    original = list(refoss_entry.options[CONF_NETWORKS])
    result = await hass.config_entries.options.async_init(refoss_entry.entry_id)
    with patch.object(
        refoss_entry.runtime_data, "async_scan", side_effect=OSError("scan failed")
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_NETWORKS: "10.8.0.0/24"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_NETWORKS: "invalid_networks"}
    assert refoss_entry.options[CONF_NETWORKS] == original


async def test_unload_closes_discovery_server(
    hass: HomeAssistant,
    fake_discovery: FakeDiscovery,
    refoss_entry: MockConfigEntry,
) -> None:
    """Test a successful unload detaches the listener and drops the singleton."""
    assert hass.data[DISCOVERY_SERVER] is fake_discovery
    assert await hass.config_entries.async_unload(refoss_entry.entry_id)
    await hass.async_block_till_done()

    assert refoss_entry.runtime_data not in fake_discovery._listeners
    assert DISCOVERY_SERVER not in hass.data
    fake_discovery.sock.close.assert_called()
    fake_discovery.transport.close.assert_called()


async def test_failed_unload_keeps_discovery_listener(
    hass: HomeAssistant,
    fake_discovery: FakeDiscovery,
    refoss_entry: MockConfigEntry,
) -> None:
    """Test a failed platform unload leaves discovery attached."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(refoss_entry.entry_id)

    assert refoss_entry.runtime_data in fake_discovery._listeners
    assert hass.data[DISCOVERY_SERVER] is fake_discovery


async def test_device_update_replaces_ip(refoss_entry: MockConfigEntry) -> None:
    """Test a discovery update with the same MAC replaces the device IP."""
    coordinator = refoss_entry.runtime_data.coordinators[0]
    coordinator.device.async_handle_update.reset_mock()

    await refoss_entry.runtime_data.device_update(build_device_mock(ip="2.2.2.2"))

    assert coordinator.device.device_info.inner_ip == "2.2.2.2"
    assert coordinator.device.async_handle_update.await_count == 1


async def test_device_update_ignores_other_mac(refoss_entry: MockConfigEntry) -> None:
    """Test a discovery update for a different MAC leaves the device IP unchanged."""
    coordinator = refoss_entry.runtime_data.coordinators[0]

    await refoss_entry.runtime_data.device_update(
        build_device_mock(ip="9.9.9.9", mac="001122334455")
    )

    assert coordinator.device.device_info.inner_ip == "1.1.1.1"
