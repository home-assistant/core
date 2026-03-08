"""Tests for JVC Projector config entry."""

from unittest.mock import AsyncMock

from jvcprojector import JvcProjectorAuthError, JvcProjectorTimeoutError

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_MAC

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test initialization."""
    mac = format_mac(MOCK_MAC)
    device = device_registry.async_get_device(identifiers={(DOMAIN, mac)})
    assert device is not None
    assert device.identifiers == {(DOMAIN, mac)}


async def test_unload_config_entry(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test config entry loading and unloading."""
    mock_config_entry = mock_integration
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_device.disconnect.call_count == 1


async def test_disconnect_on_hass_stop(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test device disconnects when Home Assistant stops."""
    assert mock_integration.state is ConfigEntryState.LOADED
    assert mock_device.disconnect.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert mock_device.disconnect.call_count == 1


async def test_config_entry_connect_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry with connect error."""
    mock_device.connect.side_effect = JvcProjectorTimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry with auth error."""
    mock_device.connect.side_effect = JvcProjectorAuthError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_migrate_legacy_sensor_entities_to_select(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration of legacy sensor entries that became selects."""
    entity_registry = er.async_get(hass)
    mac = format_mac(MOCK_MAC)
    mock_config_entry.add_to_hass(hass)

    legacy_hdr_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{mac}_hdr_processing",
        config_entry=mock_config_entry,
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{mac}_picture_mode",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(legacy_hdr_entry.entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{mac}_hdr_processing"
        )
        is None
    )

    migrated_hdr_entity_id = entity_registry.async_get_entity_id(
        Platform.SELECT, DOMAIN, f"{mac}_hdr_processing"
    )
    assert migrated_hdr_entity_id is not None
    migrated_hdr_entry = entity_registry.async_get(migrated_hdr_entity_id)
    assert migrated_hdr_entry is not None
    assert migrated_hdr_entry.disabled_by is None

    migrated_picture_mode_entity_id = entity_registry.async_get_entity_id(
        Platform.SELECT, DOMAIN, f"{mac}_picture_mode"
    )
    assert migrated_picture_mode_entity_id is not None
    migrated_picture_mode_entry = entity_registry.async_get(
        migrated_picture_mode_entity_id
    )
    assert migrated_picture_mode_entry is not None
    assert (
        migrated_picture_mode_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    )
