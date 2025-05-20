"""Common fixtures for the Paperless-ngx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pypaperless.models import RemoteVersion, Statistic
import pytest

from homeassistant.components.paperless_ngx.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import MOCK_REMOTE_VERSION_DATA_NO_UPDATE, MOCK_STATISTICS_DATA, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.paperless_ngx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_paperless() -> Generator[AsyncMock]:
    """Mock the pypaperless.Paperless client."""
    with (
        patch(
            "homeassistant.components.paperless_ngx.coordinator.Paperless",
            autospec=True,
        ) as paperless_mock,
        patch(
            "homeassistant.components.paperless_ngx.config_flow.Paperless",
            new=paperless_mock,
        ),
    ):
        paperless = paperless_mock.return_value

        paperless.base_url = "http://paperless.example.com/"
        paperless.host_version = "2.3.0"
        paperless.initialize = AsyncMock(return_value=None)
        paperless.remote_version = AsyncMock(
            return_value=RemoteVersion.create_with_data(
                paperless, data=MOCK_REMOTE_VERSION_DATA_NO_UPDATE, fetched=True
            )
        )
        paperless.statistics = AsyncMock(
            return_value=Statistic.create_with_data(
                paperless, data=MOCK_STATISTICS_DATA, fetched=True
            )
        )

        yield paperless


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="paperless_ngx_test",
        title="Paperless-ngx",
        domain=DOMAIN,
        data=USER_INPUT,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_paperless: MagicMock
) -> MockConfigEntry:
    """Set up the Tedee integration for testing."""
    await setup_integration(hass, mock_config_entry)

    return mock_config_entry
