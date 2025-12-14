"""Common fixtures for the Smart Meter B-route tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.route_b_smart_meter.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.route_b_smart_meter.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_momonga(exception=None) -> Generator[Mock]:
    """Mock for Momonga class."""

    with (
        patch(
            "homeassistant.components.route_b_smart_meter.coordinator.Momonga",
        ) as mock_momonga,
        patch(
            "homeassistant.components.route_b_smart_meter.config_flow.Momonga",
            new=mock_momonga,
        ),
    ):
        client = mock_momonga.return_value
        client.__enter__.return_value = client
        client.__exit__.return_value = None
        client.get_instantaneous_current.return_value = {
            "r phase current": 1,
            "t phase current": 2,
        }
        client.get_instantaneous_power.return_value = 3
        client.get_measured_cumulative_energy.return_value = 4
        yield mock_momonga


@pytest.fixture
def user_input() -> dict[str, str]:
    """Return test user input data."""
    return {
        CONF_DEVICE: "/dev/ttyUSB42",
        CONF_ID: "01234567890123456789012345F789",
        CONF_PASSWORD: "B_ROUTE_PASSWORD",
    }


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, user_input: dict[str, str]
) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        entry_id="01234567890123456789012345F789",
        unique_id="123456",
    )
    entry.add_to_hass(hass)
    return entry
