"""Tests for the AdGuard Home sensor entities."""

from unittest.mock import patch

from homeassistant.components.adguard.const import (
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_service_registration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard services be registered."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 5
    assert SERVICE_ADD_URL in services
    assert SERVICE_DISABLE_URL in services
    assert SERVICE_ENABLE_URL in services
    assert SERVICE_REFRESH in services
    assert SERVICE_REMOVE_URL in services


async def test_service_unregistration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    services = hass.services.async_services_for_domain(DOMAIN)
    assert len(services) == 5

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert len(services) == 0
