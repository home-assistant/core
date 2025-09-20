"""Satel Integra tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.satel_integra.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.satel_integra.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_satel() -> Generator[AsyncMock]:
    """Override the satel test."""
    with (
        patch(
            "homeassistant.components.satel_integra.AsyncSatel",
            autospec=True,
        ) as client,
        patch(
            "homeassistant.components.satel_integra.config_flow.AsyncSatel", new=client
        ),
    ):
        client.return_value.partition_states = {}
        client.return_value.violated_outputs = []
        client.return_value.violated_zones = []
        client.return_value.connect.return_value = True

        yield client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock satel configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data={CONF_HOST: "192.168.0.2", CONF_PORT: DEFAULT_PORT},
        options={CONF_CODE: 1111},
        entry_id="SATEL_INTEGRA_CONFIG_ENTRY_1",
    )
