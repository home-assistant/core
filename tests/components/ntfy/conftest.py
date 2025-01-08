"""Common fixtures for the ntfy tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ntfy.const import CONF_TOPIC, DEFAULT_URL, DOMAIN
from homeassistant.const import CONF_URL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ntfy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aiontfy() -> Generator[AsyncMock]:
    """Mock aiontfy."""

    with (
        patch("homeassistant.components.ntfy.Ntfy", autospec=True) as mock_client,
        patch("homeassistant.components.ntfy.config_flow.Ntfy", new=mock_client),
    ):
        client = mock_client.return_value

        client.publish.return_value = {}

        yield client


@pytest.fixture(autouse=True)
def mopck_random() -> Generator[AsyncMock]:
    """Mock random."""

    with patch(
        "homeassistant.components.ntfy.config_flow.random.choices",
        return_value=["mytopic"],
    ) as mock_random:
        yield mock_random.return_value


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock ntfy configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="mytopic",
        data={
            CONF_URL: DEFAULT_URL,
            CONF_TOPIC: "mytopic",
        },
        entry_id="123456789",
    )
