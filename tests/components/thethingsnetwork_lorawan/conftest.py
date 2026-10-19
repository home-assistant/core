"""Fixtures for The Things Stack connection integration."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from lorawan_connection.backend.tts import TTSConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


@pytest.fixture
def connection_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a configured connection entry."""
    entry = MockConfigEntry(
        domain="thethingsnetwork_lorawan",
        title="application",
        unique_id="https://identity:8884:application",
        data={
            "endpoint": "https://server:8884",
            "identity_server": "https://identity:8884",
            "api_key": "secret",
            "application_ids": ["application"],
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(autouse=True)
def mock_connection() -> Generator[Mock]:
    """Mock the library's transport boundary."""
    connection = Mock(spec=TTSConnection)
    connection.stack_type = "tts"
    connection.applications.return_value = {
        "application": "Application",
        "second": "Second",
    }
    connection.on_disconnect.return_value = Mock()
    connection.async_subscribe.return_value = Mock()
    with (
        patch(
            "homeassistant.components.thethingsnetwork_lorawan.TTSConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.thethingsnetwork_lorawan.config_flow.TTSConnection",
            return_value=connection,
        ),
    ):
        yield connection
