"""Common fixtures for the adguard tests."""

from unittest.mock import AsyncMock

from adguardhome.update import AdGuardHomeAvailableUpdate
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
    adguard_mock = AsyncMock()

    # static properties
    adguard_mock.host = "127.0.0.1"
    adguard_mock.port = 3000
    adguard_mock.tls = True
    adguard_mock.base_path = "/control"

    # async method mocks
    adguard_mock.version = AsyncMock(return_value="v0.107.50")
    adguard_mock.stats.dns_queries = AsyncMock(return_value=666)
    adguard_mock.stats.blocked_filtering = AsyncMock(return_value=1337)
    adguard_mock.stats.blocked_percentage = AsyncMock(return_value=200.75)
    adguard_mock.stats.replaced_parental = AsyncMock(return_value=13)
    adguard_mock.stats.replaced_safebrowsing = AsyncMock(return_value=42)
    adguard_mock.stats.replaced_safesearch = AsyncMock(return_value=18)
    adguard_mock.stats.avg_processing_time = AsyncMock(return_value=31.41)
    adguard_mock.filtering.rules_count = AsyncMock(return_value=100)
    adguard_mock.filtering.add_url = AsyncMock()
    adguard_mock.filtering.remove_url = AsyncMock()
    adguard_mock.filtering.enable_url = AsyncMock()
    adguard_mock.filtering.disable_url = AsyncMock()
    adguard_mock.filtering.refresh = AsyncMock()
    adguard_mock.update.update_available = AsyncMock(
        return_value=AdGuardHomeAvailableUpdate(
            new_version="v0.107.59",
            announcement="AdGuard Home v0.107.59 is now available!",
            announcement_url="https://github.com/AdguardTeam/AdGuardHome/releases/tag/v0.107.59",
            can_autoupdate=True,
            disabled=False,
        )
    )
    adguard_mock.update.begin_update = AsyncMock()

    return adguard_mock
