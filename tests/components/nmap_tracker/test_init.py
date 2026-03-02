"""Tests for the nmap_tracker component."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.device_tracker import DEFAULT_CONSIDER_HOME
from homeassistant.components.nmap_tracker import (
    NmapDevice,
    NmapDeviceScanner,
    NmapTrackedDevices,
)
from homeassistant.components.nmap_tracker.const import (
    CONF_HOME_INTERVAL,
    CONF_HOSTS_EXCLUDE,
    CONF_HOSTS_LIST,
    CONF_HOURS_TO_PRUNE,
    CONF_MAC_EXCLUDE,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test migrating a config entry from version 1 to version 3."""
    mock_entry = MockConfigEntry(
        unique_id="test_nmap_tracker",
        domain=DOMAIN,
        version=1,
        options={
            CONF_HOSTS: "192.168.1.0/24,192.168.2.0/24",
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: "192.168.1.1,192.168.2.2",
        },
        title="Nmap Test Tracker",
    )

    mock_entry.add_to_hass(hass)
    # Prevent the scanner from starting
    with patch(
        "homeassistant.components.nmap_tracker.NmapDeviceScanner._async_start_scanner",
        return_value=None,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Check that it has a source_id now
    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry
    assert updated_entry.version == 1
    assert updated_entry.minor_version == 3
    assert updated_entry.options == {
        CONF_EXCLUDE: "192.168.1.1,192.168.2.2",
        CONF_HOME_INTERVAL: 3,
        CONF_HOSTS: "192.168.1.0/24,192.168.2.0/24",
        CONF_HOSTS_EXCLUDE: ["192.168.1.1", "192.168.2.2"],
        CONF_HOSTS_LIST: ["192.168.1.0/24", "192.168.2.0/24"],
        CONF_HOURS_TO_PRUNE: 0,
        CONF_MAC_EXCLUDE: [],
        CONF_OPTIONS: DEFAULT_OPTIONS,
    }
    assert updated_entry.state is ConfigEntryState.LOADED


async def test_migrate_entry_fails_on_downgrade(hass: HomeAssistant) -> None:
    """Test that migration fails when user downgrades from a future version."""
    mock_entry = MockConfigEntry(
        unique_id="test_nmap_tracker",
        domain=DOMAIN,
        version=2,
        options={
            CONF_HOSTS: ["192.168.1.0/24"],
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: ["192.168.1.1"],
        },
        title="Nmap Test Tracker",
    )

    mock_entry.add_to_hass(hass)

    # Prevent the scanner from starting
    with patch(
        "homeassistant.components.nmap_tracker.NmapDeviceScanner._async_start_scanner",
        return_value=None,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Check that entry is in migration error state
    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert updated_entry
    assert updated_entry.version == 2
    assert updated_entry.state is ConfigEntryState.MIGRATION_ERROR


def _build_scanner(hass: HomeAssistant) -> tuple[NmapDeviceScanner, MockConfigEntry]:
    """Build a scanner for unit tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_HOSTS_LIST: ["192.168.1.0/24"],
            CONF_HOME_INTERVAL: 0,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_HOSTS_EXCLUDE: [],
            CONF_MAC_EXCLUDE: [],
            CONF_HOURS_TO_PRUNE: 1,
        },
        version=1,
        minor_version=3,
    )
    entry.add_to_hass(hass)
    scanner = NmapDeviceScanner(hass, entry, NmapTrackedDevices())
    scanner.consider_home = DEFAULT_CONSIDER_HOME
    scanner._hours_to_prune = 1
    return scanner, entry


async def test_prune_stale_not_home_entity(hass: HomeAssistant) -> None:
    """Test stale not_home entity is pruned if not linked to a device."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    mac = "00:00:00:00:00:01"
    ipv4 = "192.168.1.10"
    first_offline = now - timedelta(hours=3)

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        "host",
        "host",
        ipv4,
        "vendor",
        "arp-response",
        now - timedelta(hours=4),
        first_offline,
    )
    scanner.devices.ipv4_last_mac[ipv4] = mac
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, mac, config_entry=entry
    )

    scanner._async_device_offline(ipv4, "host-timeout", now)

    assert entity_registry.async_get(entity_entry.entity_id) is None
    assert mac not in scanner.devices.tracked
    assert mac not in scanner.devices.config_entry_owner
    assert ipv4 not in scanner.devices.ipv4_last_mac


async def test_do_not_prune_stale_entity_linked_to_device(hass: HomeAssistant) -> None:
    """Test stale entity is not pruned if linked to a device."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    mac = "00:00:00:00:00:02"
    ipv4 = "192.168.1.11"

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        "host",
        "host",
        ipv4,
        "vendor",
        "arp-response",
        now - timedelta(hours=4),
        now - timedelta(hours=3),
    )
    scanner.devices.ipv4_last_mac[ipv4] = mac
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "linked-device")},
    )
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        mac,
        config_entry=entry,
        device_id=device.id,
    )

    scanner._async_device_offline(ipv4, "host-timeout", now)

    assert entity_registry.async_get(entity_entry.entity_id) is not None
    assert mac in scanner.devices.tracked


async def test_do_not_prune_stale_entity_owned_by_other_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test stale entity is not pruned if owned by another config entry."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    mac = "00:00:00:00:00:22"
    ipv4 = "192.168.1.22"

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        "host",
        "host",
        ipv4,
        "vendor",
        "arp-response",
        now - timedelta(hours=4),
        now - timedelta(hours=3),
    )
    scanner.devices.ipv4_last_mac[ipv4] = mac
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    other_entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    other_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, mac, config_entry=other_entry
    )

    scanner._async_device_offline(ipv4, "host-timeout", now)

    assert entity_registry.async_get(entity_entry.entity_id) is not None
    assert mac in scanner.devices.tracked


async def test_do_not_prune_when_disabled(hass: HomeAssistant) -> None:
    """Test stale entity is not pruned if hours_to_prune is 0."""
    scanner, entry = _build_scanner(hass)
    scanner._hours_to_prune = 0
    now = dt_util.now()
    mac = "00:00:00:00:00:03"
    ipv4 = "192.168.1.12"

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        "host",
        "host",
        ipv4,
        "vendor",
        "arp-response",
        now - timedelta(hours=5),
        now - timedelta(hours=4),
    )
    scanner.devices.ipv4_last_mac[ipv4] = mac
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, mac, config_entry=entry
    )

    scanner._async_device_offline(ipv4, "host-timeout", now)

    assert entity_registry.async_get(entity_entry.entity_id) is not None
    assert mac in scanner.devices.tracked


async def test_prune_tracked_entity_missing_from_scan_results(
    hass: HomeAssistant,
) -> None:
    """Test stale tracked entity is pruned when missing from scan results."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    mac = "00:00:00:00:00:04"
    ipv4 = "192.168.1.13"

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        "host",
        "host",
        ipv4,
        "vendor",
        "arp-response",
        now - timedelta(hours=4),
        now - timedelta(hours=3),
    )
    scanner.devices.ipv4_last_mac[ipv4] = mac
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, mac, config_entry=entry
    )

    scanner._stopping = False
    scanner._excluded_hosts_this_scan = set()
    with patch.object(
        scanner,
        "_run_nmap_scan",
        return_value={
            "scan": {
                "192.168.1.20": {
                    "status": {"state": "up", "reason": "arp-response"},
                    "addresses": {"mac": "00:00:00:00:00:20"},
                    "hostnames": [],
                    "vendor": {"00:00:00:00:00:20": "Test Vendor"},
                }
            }
        },
    ):
        await scanner._async_run_nmap_scan()

    assert entity_registry.async_get(entity_entry.entity_id) is None
    assert mac not in scanner.devices.tracked
    assert mac not in scanner.devices.config_entry_owner
    assert ipv4 not in scanner.devices.ipv4_last_mac


async def test_prune_tracked_entity_without_ipv4_last_mac_mapping(
    hass: HomeAssistant,
) -> None:
    """Test stale tracked entity is pruned even without ipv4_last_mac mapping."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    mac = "00:00:00:00:00:05"
    ipv4 = "192.168.1.14"

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        "host",
        "host",
        ipv4,
        "vendor",
        "host-timeout",
        now - timedelta(hours=3),
        now - timedelta(hours=2),
    )
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, mac, config_entry=entry
    )

    scanner._async_device_offline(ipv4, "host-timeout", now)

    assert entity_registry.async_get(entity_entry.entity_id) is None
    assert mac not in scanner.devices.tracked
    assert mac not in scanner.devices.config_entry_owner


async def test_device_offline_ignores_stale_ipv4_last_mac_mapping(
    hass: HomeAssistant,
) -> None:
    """Test stale ipv4_last_mac mapping falls back to tracked device lookup."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    ipv4 = "192.168.1.15"
    stale_mac = "00:00:00:00:00:15"
    matching_mac = "00:00:00:00:00:16"

    scanner.devices.tracked[stale_mac] = NmapDevice(
        stale_mac,
        "stale-host",
        "stale-host",
        "192.168.1.200",
        "vendor",
        "arp-response",
        now - timedelta(hours=4),
        now - timedelta(hours=3),
    )
    scanner.devices.tracked[matching_mac] = NmapDevice(
        matching_mac,
        "matching-host",
        "matching-host",
        ipv4,
        "vendor",
        "arp-response",
        now - timedelta(hours=4),
        now - timedelta(hours=3),
    )
    scanner.devices.config_entry_owner[stale_mac] = entry.entry_id
    scanner.devices.config_entry_owner[matching_mac] = entry.entry_id
    scanner.devices.ipv4_last_mac[ipv4] = stale_mac

    scanner._async_device_offline(ipv4, "host-timeout", now)

    assert stale_mac in scanner.devices.tracked
    assert matching_mac not in scanner.devices.tracked
    assert ipv4 not in scanner.devices.ipv4_last_mac


async def test_prune_ungrouped_entity_missing_ipv4_after_timeout(
    hass: HomeAssistant,
) -> None:
    """Test stale ungrouped entity (no IPv4) is pruned after timeout."""
    scanner, entry = _build_scanner(hass)
    now = dt_util.now()
    mac = "00:00:00:00:00:06"

    scanner.devices.tracked[mac] = NmapDevice(
        mac,
        None,
        "host",
        None,
        "vendor",
        "Device not found in initial scan",
        now - timedelta(hours=3),
        now - timedelta(hours=2),
    )
    scanner.devices.config_entry_owner[mac] = entry.entry_id

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, mac, config_entry=entry
    )

    scanner._stopping = False
    scanner._excluded_hosts_this_scan = set()
    with patch.object(
        scanner,
        "_run_nmap_scan",
        return_value={
            "scan": {
                "192.168.1.20": {
                    "status": {"state": "up", "reason": "arp-response"},
                    "addresses": {"mac": "00:00:00:00:00:20"},
                    "hostnames": [],
                    "vendor": {"00:00:00:00:00:20": "Test Vendor"},
                }
            }
        },
    ):
        await scanner._async_run_nmap_scan()

    assert entity_registry.async_get(entity_entry.entity_id) is None
    assert mac not in scanner.devices.tracked
    assert mac not in scanner.devices.config_entry_owner
