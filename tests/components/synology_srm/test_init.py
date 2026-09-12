"""Tests for the Synology SRM __init__ module."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import synology_srm

from homeassistant.components.synology_srm.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVICE_1, DEVICE_2, MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_synology_client")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A working entry sets up, reaches LOADED, and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

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


async def test_new_device_on_scan_registers_entity(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Adding a device on a follow-up scan registers a new entity."""
    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_1]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("device_tracker", DOMAIN, "aa:bb:cc:dd:ee:01")
        is not None
    )
    assert (
        registry.async_get_entity_id("device_tracker", DOMAIN, "aa:bb:cc:dd:ee:02")
        is None
    )

    mock_synology_client.core.get_network_nsm_device.return_value = [DEVICE_1, DEVICE_2]
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        registry.async_get_entity_id("device_tracker", DOMAIN, "aa:bb:cc:dd:ee:02")
        is not None
    )


async def test_scan_error_leaves_entry_loaded(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A SynologyException during a periodic scan is logged and the entry stays loaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("device_tracker", DOMAIN, "aa:bb:cc:dd:ee:01")
        is not None
    )

    mock_synology_client.core.get_network_nsm_device.side_effect = (
        synology_srm.http.SynologyException(500, "boom")
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        registry.async_get_entity_id("device_tracker", DOMAIN, "aa:bb:cc:dd:ee:01")
        is not None
    )


async def test_ha_stop_stops_polling(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After HA stop fires, the periodic scan no longer runs."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    call_count_after_setup = mock_synology_client.core.get_network_nsm_device.call_count
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    freezer.tick(DEFAULT_SCAN_INTERVAL * 3)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        mock_synology_client.core.get_network_nsm_device.call_count
        == call_count_after_setup
    )


async def test_polling_runs_at_default_interval(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The scanner polls at DEFAULT_SCAN_INTERVAL, not sooner."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    baseline = mock_synology_client.core.get_network_nsm_device.call_count

    # Well under the interval — no new scan.
    freezer.tick(DEFAULT_SCAN_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_synology_client.core.get_network_nsm_device.call_count == baseline

    # Cross the interval — exactly one new scan.
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_synology_client.core.get_network_nsm_device.call_count == baseline + 1
