"""Tests for the AdGuard Home sensor entities."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

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


async def test_service_registration(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard services be registered."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 5
    assert SERVICE_ADD_URL in services
    assert SERVICE_DISABLE_URL in services
    assert SERVICE_ENABLE_URL in services
    assert SERVICE_REFRESH in services
    assert SERVICE_REMOVE_URL in services


async def test_service_unregistration(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    services = hass.services.async_services_for_domain(DOMAIN)
    assert len(services) == 5

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert len(services) == 0


@pytest.mark.parametrize(
    ("service", "service_call_data", "call_assertion"),
    [
        (
            SERVICE_ADD_URL,
            {"name": "Example", "url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.add_url.assert_called_once(),
        ),
        (
            SERVICE_DISABLE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.disable_url.assert_called_once(),
        ),
        (
            SERVICE_ENABLE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.enable_url.assert_called_once(),
        ),
        (
            SERVICE_REFRESH,
            {"force": False},
            lambda mock: mock.filtering.refresh.assert_called_once(),
        ),
        (
            SERVICE_REMOVE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.remove_url.assert_called_once(),
        ),
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_call_data: dict,
    call_assertion: Callable[[AsyncMock], Any],
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    await hass.services.async_call(
        DOMAIN,
        service,
        service_call_data,
        blocking=True,
    )

    call_assertion(mock_adguard)
