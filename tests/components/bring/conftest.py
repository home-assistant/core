"""Common fixtures for the Bring! tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bring import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry

EMAIL = "test-email"
PASSWORD = "test-password"

UUID = "00000000-00000000-00000000-00000000"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bring.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_bring_client() -> Generator[AsyncMock, None, None]:
    """Mock a Bring client."""
    with (
        patch(
            "homeassistant.components.bring.Bring",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.bring.config_flow.Bring",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.uuid = UUID
        client.login.return_value = True
        client.load_lists.return_value = {"lists": []}
        yield client


@pytest.fixture(name="bring_config_entry")
def mock_bring_config_entry() -> MockConfigEntry:
    """Mock bring configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}, unique_id=UUID
    )
