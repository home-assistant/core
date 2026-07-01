"""Tests for the Synology SRM __init__ module."""

from typing import Any
from unittest.mock import MagicMock

import synology_srm

from homeassistant.components.synology_srm import SynologySRMDeviceScanner
from homeassistant.components.synology_srm.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_VERIFY_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DEVICE_1, DEVICE_2, MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A working entry sets up, reaches LOADED, and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, SynologySRMDeviceScanner)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connect_failure_raises_not_ready(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-auth probe failure puts the entry into SETUP_RETRY (no reauth)."""
    mock_synology_client.core.get_network_nsm_device.side_effect = (
        synology_srm.http.SynologyException(503, "down")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not any(
        flow["context"].get("source") == "reauth"
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_setup_entry_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An auth probe failure surfaces as SETUP_ERROR and kicks off a reauth flow."""
    mock_synology_client.core.get_network_nsm_device.side_effect = (
        synology_srm.http.SynologyApiError(102, "bad auth")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"].get("source") == "reauth"
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_setup_entry_skips_disable_https_verify_when_enabled(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
) -> None:
    """disable_https_verify is not called when CONF_VERIFY_SSL is True."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_VERIFY_SSL: True},
        unique_id="verifyssl",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_synology_client.http.disable_https_verify.assert_not_called()


async def test_setup_entry_calls_disable_https_verify_when_disabled(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """disable_https_verify is called when CONF_VERIFY_SSL is False (the MOCK_CONFIG default)."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_synology_client.http.disable_https_verify.assert_called_once()


async def test_scanner_populates_devices_and_dispatches_new(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Scanner stores devices keyed by MAC and dispatches the new-device signal."""
    mock_synology_client.core.get_network_nsm_device.return_value = [
        DEVICE_1,
        DEVICE_2,
    ]
    new_signals: list[Any] = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    scanner: SynologySRMDeviceScanner = mock_config_entry.runtime_data
    async_dispatcher_connect(
        hass,
        scanner.signal_device_new,
        lambda *args: new_signals.append(args),
    )

    assert len(scanner.devices) == 2
    assert (
        scanner.signal_device_new
        == f"{DOMAIN}-{MOCK_CONFIG[CONF_HOST]}-scanned-devices"
    )
    assert (
        scanner.signal_device_update
        == f"{DOMAIN}-{MOCK_CONFIG[CONF_HOST]}-device-update"
    )

    # Adding a third device on a follow-up scan fires the new-device signal.
    mock_synology_client.core.get_network_nsm_device.return_value = [
        DEVICE_1,
        DEVICE_2,
        {"mac": "AA:BB:CC:DD:EE:99", "ip_addr": "192.168.1.99"},
    ]
    await scanner.scan_devices()
    await hass.async_block_till_done()
    assert len(new_signals) == 1
    assert len(scanner.devices) == 3


async def test_scanner_scan_error_is_swallowed(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A SynologyException during scan_devices is logged and ignored."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    scanner: SynologySRMDeviceScanner = mock_config_entry.runtime_data
    mock_synology_client.core.get_network_nsm_device.side_effect = (
        synology_srm.http.SynologyException(500, "boom")
    )
    await scanner.scan_devices()
    await hass.async_block_till_done()
    # Existing devices stay in the cache.
    assert len(scanner.devices) == 1


async def test_ha_stop_closes_scanner(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The HA stop event fires the scanner's close hook."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    scanner: SynologySRMDeviceScanner = mock_config_entry.runtime_data
    closed: list[bool] = []
    scanner.async_on_close(lambda: closed.append(True))

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert closed == [True]


async def test_scanner_uses_default_scan_interval(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Scanner uses the fixed DEFAULT_SCAN_INTERVAL, not a user-provided value."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    scanner: SynologySRMDeviceScanner = mock_config_entry.runtime_data
    assert scanner.scan_interval == DEFAULT_SCAN_INTERVAL
