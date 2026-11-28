"""Tests for the AdGuard Home sensor entities."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from adguardhome import (
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeError,
)
from probatio import Invalid
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.components.adguard.services import (
    AdGuardHomeService,
    AdGuardHomeServiceArgument,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized

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

    assert len(services) == 6
    assert AdGuardHomeService.ADD_URL in services
    assert AdGuardHomeService.PAUSE_PROTECTION in services
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
            AdGuardHomeService.PAUSE_PROTECTION,
            {AdGuardHomeServiceArgument.DURATION: {"minutes": 30}},
            lambda mock: mock.disable_protection.assert_called_once_with(
                timedelta(minutes=30)
            ),
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


async def test_pause_protection_refreshes_state(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
) -> None:
    """Test pausing protection refreshes the protection state."""
    mock_adguard.status.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        AdGuardHomeService.PAUSE_PROTECTION,
        {AdGuardHomeServiceArgument.DURATION: {"minutes": 30}},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_adguard.status.assert_called_once()


@pytest.mark.parametrize(
    "service_call_data",
    [
        pytest.param({}, id="missing"),
        pytest.param({AdGuardHomeServiceArgument.DURATION: {"seconds": 0}}, id="zero"),
        pytest.param(
            {AdGuardHomeServiceArgument.DURATION: {"seconds": -10}}, id="negative"
        ),
    ],
)
async def test_pause_protection_invalid_duration(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    service_call_data: dict[str, dict[str, int]],
) -> None:
    """Test pausing protection requires a positive duration."""
    with pytest.raises(Invalid):
        await hass.services.async_call(
            DOMAIN,
            AdGuardHomeService.PAUSE_PROTECTION,
            service_call_data,
            blocking=True,
        )

    mock_adguard.disable_protection.assert_not_called()


async def test_pause_protection_requires_admin(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    hass_read_only_user: MockUser,
) -> None:
    """Test pausing protection requires an admin user."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            AdGuardHomeService.PAUSE_PROTECTION,
            {AdGuardHomeServiceArgument.DURATION: {"minutes": 30}},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    mock_adguard.disable_protection.assert_not_called()


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
