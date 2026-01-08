"""Fixtures for Splunk tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.splunk.const import (
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.splunk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=DEFAULT_NAME,
        domain=DOMAIN,
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
        unique_id=f"{DEFAULT_HOST}:{DEFAULT_PORT}",
    )


@pytest.fixture
def mock_hass_splunk() -> Generator[MagicMock]:
    """Mock hass_splunk."""
    with (
        patch(
            "homeassistant.components.splunk.hass_splunk", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.splunk.config_flow.hass_splunk", autospec=True
        ) as mock_config_flow_client_class,
    ):
        mock_client = MagicMock()
        mock_client.check = AsyncMock(return_value=True)
        mock_client.queue = AsyncMock()

        mock_client_class.return_value = mock_client
        mock_config_flow_client_class.return_value = mock_client

        yield mock_client
