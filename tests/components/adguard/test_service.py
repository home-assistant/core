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
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.components.adguard.services import (
    AdGuardHomeService,
    AdGuardHomeServiceArgument,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
    assert AdGuardHomeService.ADD_URL in services
    assert AdGuardHomeService.DISABLE_URL in services
    assert AdGuardHomeService.ENABLE_URL in services
    assert AdGuardHomeService.REFRESH in services
    assert AdGuardHomeService.REMOVE_URL in services


@pytest.mark.parametrize(
    ("service", "service_call_data", "call_assertion"),
    [
        (
            AdGuardHomeService.ADD_URL,
            {
                AdGuardHomeServiceArgument.NAME: "Example",
                AdGuardHomeServiceArgument.URL: "https://example.com/1.txt",
            },
            lambda mock: mock.filtering.blocklists.add.assert_called_once(),
        ),
        (
            AdGuardHomeService.DISABLE_URL,
            {AdGuardHomeServiceArgument.URL: "https://example.com/1.txt"},
            lambda mock: mock.filtering.blocklists.disable.assert_called_once(),
        ),
        (
            AdGuardHomeService.ENABLE_URL,
            {AdGuardHomeServiceArgument.URL: "https://example.com/1.txt"},
            lambda mock: mock.filtering.blocklists.enable.assert_called_once(),
        ),
        (
            AdGuardHomeService.REFRESH,
            {AdGuardHomeServiceArgument.FORCE: False},
            lambda mock: mock.filtering.blocklists.refresh.assert_called_once(),
        ),
        (
            AdGuardHomeService.REMOVE_URL,
            {AdGuardHomeServiceArgument.URL: "https://example.com/1.txt"},
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
            AdGuardHomeService.ENABLE_URL,
            {AdGuardHomeServiceArgument.URL: "https://x"},
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
            AdGuardHomeService.ENABLE_URL,
            {AdGuardHomeServiceArgument.URL: "https://x"},
            blocking=True,
        )

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id
