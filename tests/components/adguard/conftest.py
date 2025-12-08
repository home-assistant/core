"""Common fixtures for the adguard tests."""

from unittest.mock import AsyncMock

from adguardhome import AdGuardHome
from adguardhome.filtering import AdGuardHomeFiltering
from adguardhome.parental import AdGuardHomeParental
from adguardhome.querylog import AdGuardHomeQueryLog
from adguardhome.safebrowsing import AdGuardHomeSafeBrowsing
from adguardhome.safesearch import AdGuardHomeSafeSearch
from adguardhome.stats import AdGuardHomeStats
from adguardhome.update import AdGuardHomeAvailableUpdate, AdGuardHomeUpdate
import pytest

from homeassistant.components.adguard import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 3000,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
        title="AdGuard Home",
    )


@pytest.fixture
async def mock_adguard() -> AsyncMock:
    """Fixture for setting up the component."""
    adguard_mock = AsyncMock(spec=AdGuardHome)
    adguard_mock.filtering = AsyncMock(spec=AdGuardHomeFiltering)
    adguard_mock.parental = AsyncMock(spec=AdGuardHomeParental)
    adguard_mock.querylog = AsyncMock(spec=AdGuardHomeQueryLog)
    adguard_mock.safebrowsing = AsyncMock(spec=AdGuardHomeSafeBrowsing)
    adguard_mock.safesearch = AsyncMock(spec=AdGuardHomeSafeSearch)
    adguard_mock.stats = AsyncMock(spec=AdGuardHomeStats)
    adguard_mock.update = AsyncMock(spec=AdGuardHomeUpdate)

    # static properties
    adguard_mock.host = "127.0.0.1"
    adguard_mock.port = 3000
    adguard_mock.tls = True
    adguard_mock.base_path = "/control"

    # async method mocks
    adguard_mock.version = AsyncMock(return_value="v0.107.50")
    adguard_mock.protection_enabled = AsyncMock(return_value=True)
    adguard_mock.parental.enabled = AsyncMock(return_value=True)
    adguard_mock.safesearch.enabled = AsyncMock(return_value=True)
    adguard_mock.safebrowsing.enabled = AsyncMock(return_value=True)
    adguard_mock.stats.dns_queries = AsyncMock(return_value=666)
    adguard_mock.stats.blocked_filtering = AsyncMock(return_value=1337)
    adguard_mock.stats.blocked_percentage = AsyncMock(return_value=200.75)
    adguard_mock.stats.replaced_parental = AsyncMock(return_value=13)
    adguard_mock.stats.replaced_safebrowsing = AsyncMock(return_value=42)
    adguard_mock.stats.replaced_safesearch = AsyncMock(return_value=18)
    adguard_mock.stats.avg_processing_time = AsyncMock(return_value=31.41)
    adguard_mock.filtering.rules_count = AsyncMock(return_value=100)
    adguard_mock.filtering.enabled = AsyncMock(return_value=True)
    adguard_mock.querylog.enabled = AsyncMock(return_value=True)
    adguard_mock.update.update_available = AsyncMock(
        return_value=AdGuardHomeAvailableUpdate(
            new_version="v0.107.59",
            announcement="AdGuard Home v0.107.59 is now available!",
            announcement_url="https://github.com/AdguardTeam/AdGuardHome/releases/tag/v0.107.59",
            can_autoupdate=True,
            disabled=False,
        )
    )

    return adguard_mock
