"""Fixtures for Schluter DITRA-HEAT tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.schluter.api import SchluterThermostat
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

DOMAIN = "schluter"

MOCK_SERIAL = "AA-BB-CC-11-22-33"

MOCK_THERMOSTAT = SchluterThermostat(
    serial_number=MOCK_SERIAL,
    name="Bathroom",
    temperature=21.5,
    set_point_temp=24.0,
    min_temp=5.0,
    max_temp=35.0,
    is_heating=True,
    is_online=True,
    load_measured_watt=150,
    sw_version="1.0.0",
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "test-password",
        },
        unique_id="user@example.com",
    )


@pytest.fixture
def mock_schluter_api() -> Generator[AsyncMock]:
    """Mock the SchluterApi used by the integration."""
    with patch("homeassistant.components.schluter.SchluterApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.async_get_session.return_value = "test-session-id"
        mock_api.async_get_thermostats.return_value = [MOCK_THERMOSTAT]
        mock_api.async_set_temperature.return_value = None
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual setup when testing the config flow."""
    with patch(
        "homeassistant.components.schluter.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
