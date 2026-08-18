"""Tests for TP-Link Omada integration services."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.services import (
    SERVICE_BLOCK_CLIENT,
    SERVICE_UNBLOCK_CLIENT,
    async_setup_services,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

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


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_BLOCK_CLIENT, "block_client", id="block"),
        pytest.param(SERVICE_UNBLOCK_CLIENT, "unblock_client", id="unblock"),
    ],
)
async def test_service_client_access_action(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test client access action service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    await hass.services.async_call(
        DOMAIN,
        service,
        {"config_entry_id": mock_config_entry.entry_id, "mac": mac},
        blocking=True,
    )

    getattr(mock_omada_site_client, method).assert_awaited_once_with(mac)


@pytest.mark.parametrize(
    ("service", "method", "error_message"),
    [
        pytest.param(
            SERVICE_BLOCK_CLIENT,
            "block_client",
            "Failed to block client with MAC AA:BB:CC:DD:EE:FF",
            id="block",
        ),
        pytest.param(
            SERVICE_UNBLOCK_CLIENT,
            "unblock_client",
            "Failed to unblock client with MAC AA:BB:CC:DD:EE:FF",
            id="unblock",
        ),
    ],
)
async def test_service_client_access_action_failure(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    error_message: str,
) -> None:
    """Test client access action service translates API errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "AA:BB:CC:DD:EE:FF"
    getattr(mock_omada_site_client, method).side_effect = OmadaClientException
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": mock_config_entry.entry_id, "mac": mac},
            blocking=True,
        )

    getattr(mock_omada_site_client, method).assert_awaited_once_with(mac)
