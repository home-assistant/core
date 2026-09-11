"""Test fixtures for volkszaehler."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.volkszaehler.const import DOMAIN, SUBENTRY_TYPE_CHANNEL
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_UUID

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.volkszaehler.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="mock_api")
def mock_client_api() -> Generator[Mock]:
    """Set up fake Volkszaehler API responses."""
    with (
        patch(
            "homeassistant.components.volkszaehler.Volkszaehler",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.volkszaehler.config_flow.Volkszaehler",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value
        api.get_data = AsyncMock(return_value=None)

        yield api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a config entry with one existing channel subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="localhost",
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 80,
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_CHANNEL,
                title="existing-uuid",
                data={CONF_UUID: "existing-uuid"},
                unique_id="existing-uuid",
                subentry_id="existing-subentry-id",
            )
        ],
    )
