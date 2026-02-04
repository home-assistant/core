"""Fixtures for Helios integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.helios.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Helios",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Helios",
        },
        unique_id=None,
    )


@pytest.fixture
def mock_helios_client() -> Generator[MagicMock]:
    """Return a mocked Helios client."""
    with patch(
        "homeassistant.components.helios.config_flow.Helios", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.fetch_metric_data = AsyncMock()
        yield client
