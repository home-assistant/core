"""Tests for TP-Link Omada integration init."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.controller import OmadaSiteController
from homeassistant.components.tplink_omada.coordinator import (
    async_cleanup_client_trackers,
    async_cleanup_devices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (
            UnsupportedControllerVersion("4.0.0"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ConnectionFailed(),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            OmadaClientException(),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_login_failed_raises_configentryauthfailed(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: OmadaClientException,
    entry_state: ConfigEntryState,
) -> None:
    """Test setup entry with login failed raises ConfigEntryAuthFailed."""
    mock_omada_client.login.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == entry_state


async def test_automatic_missing_device_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_omada_client: MagicMock,
) -> None:
    """Test missing devices are removed during initial startup cleanup.

    This validates the cleanup mechanism scheduled immediately on entry setup,
    which runs as a background task.
    """
    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")},
        manufacturer="TPLink",
        name="Old Device",
        model="Some old model",
    )

    assert device_registry.async_get(device_entry.id) == device_entry

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(device_entry.id) is None


async def test_automatic_missing_client_cleanup(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test missing client trackers are removed during initial startup cleanup.

    This validates the cleanup mechanism scheduled immediately on entry setup,
    which runs as a background task.
    """

    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_SiteId_11-11-11-11-11-11",
        config_entry=mock_config_entry,
    )

    assert entity_registry.async_get(tracker.entity_id)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(tracker.entity_id) is None


async def test_cleanup_helpers_remove_unknown_clients(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup helper removes device_tracker entities for unknown clients."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    all_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_trackers = [e for e in all_entities if e.domain == "device_tracker"]
    assert len(device_trackers) == 4

    unknown_client_entity_1 = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_99-99-99-99-99-99",
        config_entry=mock_config_entry,
    )

    unknown_client_entity_2 = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_88-88-88-88-88-88",
        config_entry=mock_config_entry,
    )

    already_disabled_entity = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_77-77-77-77-77-77",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    sensor_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="some_sensor",
        config_entry=mock_config_entry,
    )

    # Device tracker whose unique_id does not start with "scanner_" — MAC is unparsable
    malformed_no_prefix = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="tracker_00-11-22-33-44-55",
        config_entry=mock_config_entry,
    )

    # Device tracker whose unique_id has only two underscore-separated parts — MAC is unparsable
    malformed_wrong_parts = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_notype",
        config_entry=mock_config_entry,
    )

    await async_cleanup_client_trackers(hass, controller)

    assert entity_registry.async_get(unknown_client_entity_1.entity_id) is None
    assert entity_registry.async_get(unknown_client_entity_2.entity_id) is None
    assert entity_registry.async_get(already_disabled_entity.entity_id) is None
    assert entity_registry.async_get(sensor_entity.entity_id) is not None
    assert entity_registry.async_get(malformed_no_prefix.entity_id) is not None
    assert entity_registry.async_get(malformed_wrong_parts.entity_id) is not None


async def test_cleanup_devices_removes_orphans(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cleanup helper removes orphaned device registry entries."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    orphan = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")},
        manufacturer="TP-Link",
        model="Test",
        name="Orphan",
    )
    assert device_registry.async_get(orphan.id)

    await async_cleanup_devices(hass, controller)

    assert device_registry.async_get(orphan.id) is None


async def test_cleanup_lock_prevents_redundant_tasks(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cleanup lock prevents scheduling a second cleanup while one is running."""
    cleanup_call_count = 0
    cleanup_started = asyncio.Event()
    cleanup_proceed = asyncio.Event()

    async def blocking_cleanup(h: HomeAssistant, c: OmadaSiteController) -> None:
        nonlocal cleanup_call_count
        cleanup_call_count += 1
        cleanup_started.set()
        await cleanup_proceed.wait()

    with patch(
        "homeassistant.components.tplink_omada.async_cleanup_devices",
        new=blocking_cleanup,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Startup _schedule_cleanup() fires immediately; wait for it to acquire lock
        await cleanup_started.wait()

        # Lock is now held — the 1-hour interval firing should be a no-op
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
        await hass.async_block_till_done()

        # Release the first cleanup
        cleanup_proceed.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    # The second _schedule_cleanup call returned early due to the lock guard
    assert cleanup_call_count == 1


async def test_cleanup_runs_hourly(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test stale client trackers are removed on the hourly interval."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Add a stale tracker after initial startup cleanup has already run
    stale_tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_11-11-11-11-11-11",
        config_entry=mock_config_entry,
    )
    assert entity_registry.async_get(stale_tracker.entity_id) is not None

    # Fire the 1-hour interval to trigger cleanup again
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(hours=1, seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(stale_tracker.entity_id) is None
