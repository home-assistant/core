"""ComfoConnect tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.comfoconnect import (
    CONF_USER_AGENT,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.comfoconnect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_comfoconnect_bridge() -> Generator[AsyncMock]:
    """Mock a Comfoconnect bridge."""
    with (
        patch(
            "homeassistant.components.comfoconnect.Bridge",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.comfoconnect.config_flow.Bridge",
            new=mock_client,
        ),
    ):
        mock_bridge = AsyncMock()
        mock_bridge.uuid = b"00"
        mock_client.discover.return_value = [mock_bridge]
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
        unique_id="3030",
    )
