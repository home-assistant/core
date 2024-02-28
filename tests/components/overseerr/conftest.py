"""Common fixtures for the Overseerr tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from overseerr_api.models import RequestCountGet200Response
import pytest

from homeassistant.components.overseerr.const import DEFAULT_URL, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def fixture_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_URL: DEFAULT_URL, CONF_API_KEY: "test-api-key"},
        version=1,
    )


@pytest.fixture(name="overseerr_request_data")
def fixture_overseerr_request_data() -> Generator[None, MagicMock, None]:
    """Return a mocked OverseerrRequestData."""
    with patch(
        "homeassistant.components.overseerr.coordinator.OverseerrRequestData",
        autospec=True,
    ) as overseeerr_mock:
        overseerr = overseeerr_mock.return_value
        overseerr.request_count = RequestCountGet200Response()
        yield overseerr


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.overseerr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_validate_input() -> Generator[Mock, None, None]:
    """Mock the validate_input method."""
    with patch(
        "homeassistant.components.overseerr.config_flow.OverseerrConfigFlow.validate_input",
        return_value={},
    ) as mock_validate_input:
        yield mock_validate_input
