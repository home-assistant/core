"""Common fixtures for the Paperless-ngx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pypaperless.models import RemoteVersion, Statistic, Status
import pytest

from homeassistant.components.paperless_ngx.const import DOMAIN

from .const import (
    MOCK_REMOTE_VERSION_DATA,
    MOCK_STATISTICS_DATA,
    MOCK_STATUS_DATA,
    PAPERLESS_IMPORT_PATHS,
    USER_INPUT,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.paperless_ngx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_client() -> Generator[AsyncMock]:
    """Mock the pypaperless.Paperless client."""
    patchers = [patch(path, autospec=True) for path in PAPERLESS_IMPORT_PATHS]

    with patchers[0] as mock1, patchers[1] as mock2, patchers[2] as mock3:
        mock_instance = AsyncMock()
        dummy_api = MagicMock()

        mock_instance.initialize = AsyncMock(return_value=None)
        mock_instance.status = AsyncMock(
            return_value=Status.create_with_data(dummy_api, data=MOCK_STATUS_DATA)
        )
        mock_instance.statistics = AsyncMock(
            return_value=Statistic.create_with_data(
                dummy_api, data=MOCK_STATISTICS_DATA
            )
        )
        mock_instance.remote_version = AsyncMock(
            return_value=RemoteVersion.create_with_data(
                dummy_api, data=MOCK_REMOTE_VERSION_DATA
            )
        )

        for mock_paperless in tuple(mock1, mock2, mock3):
            mock_paperless.return_value = mock_instance
            mock_paperless.return_value.__aenter__.return_value = mock_instance
            mock_paperless.return_value.initialize = mock_instance.initialize
            mock_paperless.return_value.remote_version = mock_instance.remote_version
            mock_paperless.return_value.status = mock_instance.status
            mock_paperless.return_value.statistics = mock_instance.statistics

        yield mock_instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="paperless_ngx_test",
        title="Paperless-ngx",
        domain=DOMAIN,
        data=USER_INPUT,
    )
