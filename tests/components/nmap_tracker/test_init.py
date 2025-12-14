"""Tests for the nmap_tracker component."""

from unittest.mock import patch

from homeassistant.components.nmap_tracker.const import (
    CONF_HOME_INTERVAL,
    CONF_HOSTS_EXCLUDE,
    CONF_HOSTS_LIST,
    CONF_MAC_EXCLUDE,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test migrating a config entry from version 1 to version 2."""
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
    assert updated_entry.minor_version == 2
    assert updated_entry.options == {
        CONF_EXCLUDE: "192.168.1.1,192.168.2.2",
        CONF_HOME_INTERVAL: 3,
        CONF_HOSTS: "192.168.1.0/24,192.168.2.0/24",
        CONF_HOSTS_EXCLUDE: ["192.168.1.1", "192.168.2.2"],
        CONF_HOSTS_LIST: ["192.168.1.0/24", "192.168.2.0/24"],
        CONF_MAC_EXCLUDE: [],
        CONF_OPTIONS: DEFAULT_OPTIONS,
    }
    assert updated_entry.state == ConfigEntryState.LOADED


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
    assert updated_entry.state == ConfigEntryState.MIGRATION_ERROR
