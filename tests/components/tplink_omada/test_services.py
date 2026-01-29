"""Tests for TP-Link Omada integration services."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.services import async_setup_services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

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


async def test_service_cleanup_client_trackers_all_entities(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cleanup client trackers service removes unknown clients."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # At this point, entities have been created by the integration for all known clients
    # Let's find one of those and two unknown ones to test
    all_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_trackers = [e for e in all_entities if e.domain == "device_tracker"]

    # Should have 4 device trackers from fixture
    assert len(device_trackers) == 4

    # Add two unknown clients (not in Omada)
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

    # Add unknown client already disabled (should not be touched)
    already_disabled_entity = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_77-77-77-77-77-77",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    # Add a non-device_tracker entity (should be ignored)
    sensor_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="some_sensor",
        config_entry=mock_config_entry,
    )

    # Verify initial state - note known_client_entity may be disabled by default
    # but the others should be as we set them
    assert not unknown_client_entity_1.disabled
    assert not unknown_client_entity_2.disabled
    assert already_disabled_entity.disabled
    assert not sensor_entity.disabled

    # Call the cleanup service (no entity_id = all entities)
    await hass.services.async_call(
        DOMAIN,
        "cleanup_client_trackers",
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify results
    # Unknown clients should be removed (deleted)
    assert entity_registry.async_get(unknown_client_entity_1.entity_id) is None
    assert entity_registry.async_get(unknown_client_entity_2.entity_id) is None

    # Already disabled entity should also be removed
    assert entity_registry.async_get(already_disabled_entity.entity_id) is None

    # Sensor should remain unaffected
    assert entity_registry.async_get(sensor_entity.entity_id) is not None


async def test_service_cleanup_client_trackers_single_entity(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cleanup can target a single specific entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # Create two unknown clients
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

    # Target only one entity for cleanup
    await hass.services.async_call(
        DOMAIN,
        "cleanup_client_trackers",
        {"entity_id": unknown_1.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Only targeted entity should be removed
    assert entity_registry.async_get(unknown_1.entity_id) is None
    # Other unknown entity should remain
    assert entity_registry.async_get(unknown_2.entity_id) is not None
