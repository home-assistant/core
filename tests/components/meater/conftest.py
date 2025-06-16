"""Meater tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.meater.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.meater.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_meater_client() -> Generator[AsyncMock]:
    """Mock a Meater client."""
    with (
        patch(
            "homeassistant.components.meater.coordinator.MeaterApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.meater.config_flow.MeaterApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Meater",
        data={CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"},
        unique_id="user@host.com",
    )
