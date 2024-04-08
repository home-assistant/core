"""Common fixtures for the pyLoad tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyloadapi.types import StatusServerResponse
import pytest

from homeassistant.components.pyload import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

TEST_USER_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PORT: 8000,
    CONF_SSL: True,
    CONF_VERIFY_SSL: True,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pyload.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pyloadapi() -> Generator[AsyncMock, None, None]:
    """Mock a PyLoadAPI."""
    with (
        patch(
            "homeassistant.components.pyload.PyLoadAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.pyload.config_flow.PyLoadAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = True
        client.get_status.return_value = StatusServerResponse
        yield client


@pytest.fixture(name="pyload_config_entry")
def mock_pyload_config_entry() -> MockConfigEntry:
    """Mock bring configuration entry."""
    url = f"https://{TEST_USER_DATA[CONF_HOST]}:{TEST_USER_DATA[CONF_PORT]}/"
    return MockConfigEntry(
        domain=DOMAIN, data={**TEST_USER_DATA, CONF_URL: url}, unique_id=url
    )
