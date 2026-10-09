"""Common fixtures for the adguard tests."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from adguardhome import (
    AdGuardHome,
    AvailableUpdate,
    FilteringConfig,
    FilterList,
    QueryLogConfig,
    SafeSearchConfig,
    Stats,
    Status,
    TimeUnit,
)
from adguardhome.filtering import AdGuardHomeFiltering, FilterLists
from adguardhome.querylog import AdGuardHomeQueryLog
from adguardhome.safesearch import AdGuardHomeSafeSearch
from adguardhome.stats import AdGuardHomeStats
from adguardhome.toggle import Toggle
from adguardhome.update import AdGuardHomeUpdate
from awesomeversion import AwesomeVersion
import pytest

from homeassistant.components.adguard import DOMAIN, PLATFORMS
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

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
def mock_adguard() -> Generator[AsyncMock]:
    """Return a mocked AdGuard Home client."""
    adguard_mock = AsyncMock(spec=AdGuardHome)
    adguard_mock.filtering = AsyncMock(spec=AdGuardHomeFiltering)
    adguard_mock.filtering.blocklists = AsyncMock(spec=FilterLists)
    adguard_mock.parental = AsyncMock(spec=Toggle)
    adguard_mock.querylog = AsyncMock(spec=AdGuardHomeQueryLog)
    adguard_mock.safebrowsing = AsyncMock(spec=Toggle)
    adguard_mock.safesearch = AsyncMock(spec=AdGuardHomeSafeSearch)
    adguard_mock.stats = AsyncMock(spec=AdGuardHomeStats)
    adguard_mock.update = AsyncMock(spec=AdGuardHomeUpdate)

    # async method mocks
    adguard_mock.status = AsyncMock(
        return_value=Status(
            version=AwesomeVersion("v0.107.50"),
            running=True,
            language="en",
            dns_addresses=("127.0.0.1",),
            dns_port=53,
            http_port=3000,
            protection_enabled=True,
        )
    )
    adguard_mock.parental.enabled = AsyncMock(return_value=True)
    adguard_mock.safesearch.config = AsyncMock(
        return_value=SafeSearchConfig(enabled=True)
    )
    adguard_mock.safebrowsing.enabled = AsyncMock(return_value=True)
    adguard_mock.stats.get = AsyncMock(
        return_value=Stats(
            dns_queries=666,
            blocked_filtering=1337,
            blocked_safebrowsing=42,
            blocked_parental=13,
            enforced_safesearch=18,
            avg_processing_time=timedelta(milliseconds=31.41),
            time_unit=TimeUnit.HOURS,
        )
    )
    adguard_mock.filtering.blocklists.list = AsyncMock(
        return_value=(
            FilterList(
                id=1,
                name="AdGuard DNS filter",
                url="https://example.com/filter.txt",
                enabled=True,
                rules_count=100,
            ),
        )
    )
    adguard_mock.filtering.config = AsyncMock(
        return_value=FilteringConfig(enabled=True, update_interval=timedelta(hours=24))
    )
    adguard_mock.querylog.config = AsyncMock(
        return_value=QueryLogConfig(
            enabled=True,
            retention=timedelta(days=90),
            anonymize_client_ip=False,
        )
    )
    adguard_mock.update.get = AsyncMock(
        return_value=AvailableUpdate(
            new_version=AwesomeVersion("v0.107.59"),
            announcement="AdGuard Home v0.107.59 is now available!",
            announcement_url="https://github.com/AdguardTeam/AdGuardHome/releases/tag/v0.107.59",
            can_autoupdate=True,
            disabled=False,
        )
    )

    with patch(
        "homeassistant.components.adguard.AdGuardHome",
        return_value=adguard_mock,
    ):
        yield adguard_mock


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_adguard: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the AdGuard Home integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.adguard.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
