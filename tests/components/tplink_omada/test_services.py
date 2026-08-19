"""Tests for TP-Link Omada integration services."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import POLL_CLIENTS
from homeassistant.components.tplink_omada.services import (
    SERVICE_BLOCK,
    SERVICE_RECONNECT,
    SERVICE_UNBLOCK,
    async_setup_services,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


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
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
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
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
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
    """Test reconnect client service raises correct exception on failure."""

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


@pytest.mark.usefixtures("mock_omada_clients_only_client")
@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_RECONNECT, "reconnect_client", id="reconnect"),
        pytest.param(SERVICE_BLOCK, "block_client", id="block"),
        pytest.param(SERVICE_UNBLOCK, "unblock_client", id="unblock"),
    ],
)
async def test_service_client_access_action(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    service: str,
    method: str,
) -> None:
    """Test client action service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_registry.async_update_entity("device_tracker.banana", disabled_by=None)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=POLL_CLIENTS + 10))
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        service,
        target={"entity_id": "device_tracker.banana"},
        blocking=True,
    )

    getattr(mock_omada_clients_only_site_client, method).assert_awaited_once_with(
        "2C-71-FF-ED-34-83"
    )


@pytest.mark.usefixtures("mock_omada_clients_only_client")
@pytest.mark.parametrize(
    ("service", "method", "error_message"),
    [
        pytest.param(
            SERVICE_RECONNECT,
            "reconnect_client",
            "Failed to reconnect client with MAC 2C-71-FF-ED-34-83",
            id="reconnect",
        ),
        pytest.param(
            SERVICE_BLOCK,
            "block_client",
            "Failed to block client with MAC 2C-71-FF-ED-34-83",
            id="block",
        ),
        pytest.param(
            SERVICE_UNBLOCK,
            "unblock_client",
            "Failed to unblock client with MAC 2C-71-FF-ED-34-83",
            id="unblock",
        ),
    ],
)
async def test_service_client_access_action_failure(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    service: str,
    method: str,
    error_message: str,
) -> None:
    """Test client action service translates API errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_registry.async_update_entity("device_tracker.banana", disabled_by=None)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=POLL_CLIENTS + 10))
    await hass.async_block_till_done()

    getattr(mock_omada_clients_only_site_client, method).side_effect = OmadaClientException
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            DOMAIN,
            service,
            target={"entity_id": "device_tracker.banana"},
            blocking=True,
        )

    getattr(mock_omada_clients_only_site_client, method).assert_awaited_once_with(
        "2C-71-FF-ED-34-83"
    )
