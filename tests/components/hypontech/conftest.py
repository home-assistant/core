"""Common fixtures for the Hypontech Cloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from hyponcloud import AdminInfo
import pytest

from homeassistant.components.hypontech.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hypontech.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
        unique_id="mock_account_id_123",
    )


@pytest.fixture
def mock_hyponcloud() -> Generator[AsyncMock]:
    """Mock HyponCloud."""
    with (
        patch(
            "homeassistant.components.hypontech.HyponCloud", autospec=True
        ) as mock_hyponcloud,
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud",
            new=mock_hyponcloud,
        ),
    ):
        mock_client = mock_hyponcloud.return_value
        get_admin_info = AsyncMock(spec=AdminInfo)
        get_admin_info.id = "mock_account_id_123"
        mock_client.get_admin_info.return_value = get_admin_info
        mock_client.get_list.return_value = []
        yield mock_client
