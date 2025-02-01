"""Configuration for Velux tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.velux import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.velux.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_velux_client() -> Generator[AsyncMock]:
    """Mock a Velux client."""
    with (
        patch(
            "homeassistant.components.velux.config_flow.PyVLX",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        yield client


@pytest.fixture
def mock_user_config_entry() -> MockConfigEntry:
    """Return the user config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )


@pytest.fixture
def mock_discovered_config_entry() -> MockConfigEntry:
    """Return the user config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
            CONF_MAC: "64:61:84:00:ab:cd",
        },
        unique_id="VELUX_KLF_ABCD",
    )
