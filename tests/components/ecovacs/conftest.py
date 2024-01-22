"""Common fixtures for the Ecovacs tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator
from deebot_client.models import Credentials
import pytest

from homeassistant.components.ecovacs.const import DOMAIN

from .const import VALID_ENTRY_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecovacs.async_setup_entry", return_value=True
    ) as async_setup_entry:
        yield async_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="username",
        domain=DOMAIN,
        data=VALID_ENTRY_DATA,
    )


@pytest.fixture
def mock_authenticator() -> Generator[Mock, None, None]:
    """Mock the authenticator."""
    mock_authenticator = Mock(spec_set=Authenticator)
    mock_authenticator.authenticate.return_value = Credentials("token", "user_id", 0)
    with patch(
        "homeassistant.components.ecovacs.controller.Authenticator",
        return_value=mock_authenticator,
    ), patch(
        "homeassistant.components.ecovacs.config_flow.Authenticator",
        return_value=mock_authenticator,
    ):
        yield mock_authenticator


@pytest.fixture
def mock_authenticator_authenticate(mock_authenticator: Mock) -> AsyncMock:
    """Mock authenticator.authenticate."""
    return mock_authenticator.authenticate


@pytest.fixture
def mock_api_client(mock_authenticator: Mock) -> Mock:
    """Mock the API client."""
    with patch(
        "homeassistant.components.ecovacs.controller.ApiClient",
        return_value=Mock(spec_set=ApiClient),
    ) as mock_api_client:
        yield mock_api_client.return_value
