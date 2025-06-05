"""Common fixtures for the Paperless-ngx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pypaperless.models import RemoteVersion, Statistic, Status
import pytest

from homeassistant.components.paperless_ngx.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import USER_INPUT_ONE

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_status_data() -> Generator[MagicMock]:
    """Return test status data."""
    return load_json_object_fixture("test_data_status.json", DOMAIN)


@pytest.fixture
def mock_remote_version_data() -> Generator[MagicMock]:
    """Return test remote version data."""
    return load_json_object_fixture("test_data_remote_version.json", DOMAIN)


@pytest.fixture
def mock_remote_version_data_unavailable() -> Generator[MagicMock]:
    """Return test remote version data."""
    return load_json_object_fixture("test_data_remote_version_unavailable.json", DOMAIN)


@pytest.fixture
def mock_statistic_data() -> Generator[MagicMock]:
    """Return test statistic data."""
    return load_json_object_fixture("test_data_statistic.json", DOMAIN)


@pytest.fixture
def mock_statistic_data_update() -> Generator[MagicMock]:
    """Return updated test statistic data."""
    return load_json_object_fixture("test_data_statistic_update.json", DOMAIN)


@pytest.fixture(autouse=True)
def mock_paperless(
    mock_statistic_data: MagicMock,
    mock_status_data: MagicMock,
    mock_remote_version_data: MagicMock,
) -> Generator[AsyncMock]:
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
        patch(
            "homeassistant.components.paperless_ngx.Paperless",
            new=paperless_mock,
        ),
    ):
        paperless = paperless_mock.return_value

        paperless.base_url = "http://paperless.example.com/"
        paperless.host_version = "2.3.0"
        paperless.initialize.return_value = None
        paperless.statistics = AsyncMock(
            return_value=Statistic.create_with_data(
                paperless, data=mock_statistic_data, fetched=True
            )
        )
        paperless.status = AsyncMock(
            return_value=Status.create_with_data(
                paperless, data=mock_status_data, fetched=True
            )
        )
        paperless.remote_version = AsyncMock(
            return_value=RemoteVersion.create_with_data(
                paperless, data=mock_remote_version_data, fetched=True
            )
        )

        yield paperless


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="0KLG00V55WEVTJ0CJHM0GADNGH",
        title="Paperless-ngx",
        domain=DOMAIN,
        data=USER_INPUT_ONE,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_paperless: MagicMock
) -> MockConfigEntry:
    """Set up the Paperless-ngx integration for testing."""
    await setup_integration(hass, mock_config_entry)

    return mock_config_entry
