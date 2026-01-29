"""Tests for TP-Link Omada integration services."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.tplink_omada.cleanup import (
    async_cleanup_client_trackers,
    async_cleanup_devices,
)
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.services import async_setup_services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_service_reconnect_no_config_entries(
    hass: HomeAssistant,
) -> None:
    """Test reconnect service raises error when no config entries exist."""
    # Register services directly without any config entries
    async_setup_services(hass)

    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(
        ServiceValidationError, match="No active TP-Link Omada controllers found"
    ):
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"mac": mac},
            blocking=True,
        )


async def test_service_reconnect_client(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect client service."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    await hass.services.async_call(
        DOMAIN,
        "reconnect_client",
        {"config_entry_id": mock_config_entry.entry_id, "mac": mac},
        blocking=True,
    )

    mock_omada_site_client.reconnect_client.assert_awaited_once_with(mac)


async def test_service_reconnect_failed_with_invalid_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect with invalid config entry raises ServiceValidationError."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(
        ServiceValidationError, match="Specified TP-Link Omada controller not found"
    ):
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"config_entry_id": "invalid_entry_id", "mac": mac},
            blocking=True,
        )


async def test_service_reconnect_without_config_entry_id(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect client service without config_entry_id uses first loaded entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    await hass.services.async_call(
        DOMAIN,
        "reconnect_client",
        {"mac": mac},
        blocking=True,
    )

    mock_omada_site_client.reconnect_client.assert_awaited_once_with(mac)


async def test_service_reconnect_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect service raises error when entry is not loaded."""
    # Set up first entry so service is registered
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_entry = MockConfigEntry(
        title="Unloaded Omada Controller",
        domain=DOMAIN,
        unique_id="67890",
    )
    unloaded_entry.add_to_hass(hass)

    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(
        ServiceValidationError,
        match="The TP-Link Omada integration is not currently available",
    ):
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"config_entry_id": unloaded_entry.entry_id, "mac": mac},
            blocking=True,
        )


async def test_service_reconnect_failed_raises_homeassistanterror(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconnect client service raises the right kind of exception on service failure."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    mock_omada_site_client.reconnect_client.side_effect = OmadaClientException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "reconnect_client",
            {"config_entry_id": mock_config_entry.entry_id, "mac": mac},
            blocking=True,
        )

    mock_omada_site_client.reconnect_client.assert_awaited_once_with(mac)


async def test_cleanup_helpers_remove_unknown_clients(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test helper removes entities for unknown clients."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

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

    assert not unknown_client_entity_1.disabled
    assert not unknown_client_entity_2.disabled
    assert already_disabled_entity.disabled
    assert not sensor_entity.disabled

    await async_cleanup_client_trackers(
        hass,
        config_entry_ids={mock_config_entry.entry_id},
        raise_on_error=True,
    )

    assert entity_registry.async_get(unknown_client_entity_1.entity_id) is None
    assert entity_registry.async_get(unknown_client_entity_2.entity_id) is None
    assert entity_registry.async_get(already_disabled_entity.entity_id) is None
    assert entity_registry.async_get(sensor_entity.entity_id) is not None


async def test_cleanup_helpers_target_specific_entity(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cleanup helper can target individual entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    unknown_1 = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_11-11-11-11-11-11",
        config_entry=mock_config_entry,
    )

    unknown_2 = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_22-22-22-22-22-22",
        config_entry=mock_config_entry,
    )

    await async_cleanup_client_trackers(
        hass,
        entity_ids=[unknown_1.entity_id],
        raise_on_error=True,
    )

    assert entity_registry.async_get(unknown_1.entity_id) is None
    assert entity_registry.async_get(unknown_2.entity_id) is not None


async def test_cleanup_devices_removes_orphans(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure orphaned devices are removed by the helper."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    orphan = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")},
        manufacturer="TP-Link",
        model="Test",
        name="Orphan",
    )
    assert device_registry.async_get(orphan.id)

    await async_cleanup_devices(
        hass,
        config_entry_ids={mock_config_entry.entry_id},
    )

    assert device_registry.async_get(orphan.id) is None
