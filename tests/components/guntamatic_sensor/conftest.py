"""Common fixtures for the guntamatic tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.guntamatic_sensor.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    "Boiler temperature": ["14.09", "°C"],
    "Outside Temp.": ["15.95", "°C"],
    "Buffer load.": ["22", "%"],
    "Program": ["HEAT", ""],
    "Running": ["Service Ign.", ""],
    "Serial": ["959103", ""],
    "Version": ["32a", ""],
}


@pytest.fixture
def mock_heater() -> Generator[AsyncMock]:
    """Mock the Heater class."""
    with patch(
        "homeassistant.components.guntamatic_sensor.Heater",
        autospec=True,
    ) as mock:
        mock.return_value.get_data = MagicMock(return_value=MOCK_DATA)
        mock.return_value.host = "1.1.1.1"
        yield mock


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.guntamatic_sensor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
