"""Common fixtures for the Portainer tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.portainer.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_portainer() -> Generator[MagicMock]:
    """Mock APSystems lib."""
    with (
        patch(
            "homeassistant.components.portainer.PortainerClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.portainer.config_flow.PortainerClient",
            new=mock_client,
        ),
    ):
        mock_api = mock_client.return_value
        mock_api.get_status.return_value = MagicMock()
        yield mock_api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
        },
        unique_id="MY_SERIAL_NUMBER",
    )
