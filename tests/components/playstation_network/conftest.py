"""Common fixtures for the Playstation Network tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN

from tests.common import MockConfigEntry

NPSSO_TOKEN: str = "npsso-token"
PSN_ID: str = "my-psn-id"


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock PlayStation Network configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-user",
        data={
            CONF_NPSSO: NPSSO_TOKEN,
        },
        unique_id=PSN_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.playstation_network.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_user() -> Generator[MagicMock]:
    """Mock psnawp_api User object."""

    with patch(
        "homeassistant.components.playstation_network.config_flow.User", autospec=True
    ) as mock_client:
        client = mock_client.return_value

        client.account_id = PSN_ID
        client.online_id = "testuser"

        yield client


@pytest.fixture
def mock_psnawpapi(mock_user: MagicMock) -> Generator[MagicMock]:
    """Mock psnawp_api."""

    with (
        patch(
            "homeassistant.components.playstation_network.PlaystationNetwork",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.playstation_network.config_flow.PlaystationNetwork",
            new=mock_client,
        ),
    ):
        mock_client.parse_npsso_token.side_effect = lambda x: x
        client = mock_client.return_value

        client.get_user.return_value = mock_user

        yield client
