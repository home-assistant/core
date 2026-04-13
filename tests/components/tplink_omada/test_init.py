"""Tests for TP-Link Omada integration init."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import (
    async_cleanup_client_trackers,
    async_cleanup_devices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

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
    """Test missing devices are removed on coordinator data refresh.

    This validates the cleanup mechanism that runs during coordinator refresh,
    which is triggered during initial setup.
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
    """Test missing client trackers are removed on coordinator data refresh.

    This validates the cleanup mechanism that runs during coordinator refresh,
    which is triggered during initial setup.
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
        unique_id="scanner_Default_11-11-11-11-11-11",
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

    await async_cleanup_client_trackers(hass, controller, raise_on_error=True)

    assert entity_registry.async_get(unknown_client_entity_1.entity_id) is None
    assert entity_registry.async_get(unknown_client_entity_2.entity_id) is None
    assert entity_registry.async_get(already_disabled_entity.entity_id) is None
    assert entity_registry.async_get(sensor_entity.entity_id) is not None


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
