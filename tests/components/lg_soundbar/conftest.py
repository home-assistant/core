"""Common fixtures for the lg_soundbar tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lg_soundbar.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from . import set_answers


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="LG Soundbar",
        data={CONF_HOST: "127.0.0.1", CONF_PORT: DEFAULT_PORT},
        unique_id="uuid",
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the aiotemescal client of a connected soundbar.

    Only the client is mocked so that the real ``functions`` and
    ``equalisers`` lookup tables remain available to the media player.
    """
    with (
        patch(
            "homeassistant.components.lg_soundbar.TemescalClient", autospec=True
        ) as client_class,
        patch(
            "homeassistant.components.lg_soundbar.config_flow.TemescalClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.connected = True
        client.reports_power = True
        client.__aenter__.return_value = client
        set_answers(
            client,
            {
                "SPK_LIST_VIEW_INFO": {"s_user_name": "name"},
                "MAC_INFO_DEV": {"s_uuid": "uuid"},
            },
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip setting up the entry created by the config flow."""
    with patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup
