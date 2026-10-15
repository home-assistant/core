"""Tests for the AdGuard Home sensor entities."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

from adguardhome import (
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeError,
)
import pytest

from homeassistant.components.adguard.const import (
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


async def test_service_registration(
    hass: HomeAssistant,
) -> None:
    """Test the adguard services be registered."""
    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 5
    assert SERVICE_ADD_URL in services
    assert SERVICE_DISABLE_URL in services
    assert SERVICE_ENABLE_URL in services
    assert SERVICE_REFRESH in services
    assert SERVICE_REMOVE_URL in services


@pytest.mark.parametrize(
    ("service", "service_call_data", "call_assertion"),
    [
        (
            SERVICE_ADD_URL,
            {"name": "Example", "url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.blocklists.add.assert_called_once(),
        ),
        (
            SERVICE_DISABLE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.blocklists.disable.assert_called_once(),
        ),
        (
            SERVICE_ENABLE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.blocklists.enable.assert_called_once(),
        ),
        (
            SERVICE_REFRESH,
            {"force": False},
            lambda mock: mock.filtering.blocklists.refresh.assert_called_once(),
        ),
        (
            SERVICE_REMOVE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.blocklists.remove.assert_called_once(),
        ),
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    service: str,
    service_call_data: dict,
    call_assertion: Callable[[AsyncMock], Any],
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    await hass.services.async_call(
        DOMAIN,
        service,
        service_call_data,
        blocking=True,
    )

    call_assertion(mock_adguard)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            AdGuardHomeConnectionError("Boom"),
            "Could not connect to AdGuard Home",
        ),
        (
            AdGuardHomeAuthenticationError("Nope"),
            "AdGuard Home rejected the credentials. Please reauthenticate with a "
            "valid username and password",
        ),
        (
            AdGuardHomeError("AdGuard Home has no blocklist with URL https://x"),
            "AdGuard Home could not complete the action: "
            "AdGuard Home has no blocklist with URL https://x",
        ),
    ],
)
async def test_service_error(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    error: Exception,
    message: str,
) -> None:
    """Test a failing action raises a translated error, not the library one."""
    mock_adguard.filtering.blocklists.enable.side_effect = error

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_URL,
            {"url": "https://x"},
            blocking=True,
        )

    assert str(excinfo.value) == message


async def test_service_authentication_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test rejected credentials during an action ask for new ones."""
    mock_adguard.filtering.blocklists.enable.side_effect = (
        AdGuardHomeAuthenticationError("Nope")
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_URL,
            {"url": "https://x"},
            blocking=True,
        )

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id
