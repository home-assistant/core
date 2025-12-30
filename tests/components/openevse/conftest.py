"""Test Fixtures for the OpenEVSE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_charger():
    """Create a mock OpenEVSE charger."""
    with patch(
        "homeassistant.components.openevse.config_flow.openevsewifi.Charger"
    ) as mock:
        charger = MagicMock()
        charger.getStatus.return_value = "Charging"
        charger.getChargeTimeElapsed.return_value = 3600  # 60 minutes in seconds
        charger.getAmbientTemperature.return_value = 25.5
        charger.getIRTemperature.return_value = 30.2
        charger.getRTCTemperature.return_value = 28.7
        charger.getUsageSession.return_value = 15000  # 15 kWh in Wh
        charger.getUsageTotal.return_value = 500000  # 500 kWh in Wh
        charger.charging_current = 32.0
        mock.return_value = charger
        yield charger


@pytest.fixture
def mock_bad_charger():
    """Create a mock OpenEVSE charger."""
    with patch(
        "homeassistant.components.openevse.config_flow.openevsewifi.Charger"
    ) as mock:
        charger = MagicMock()
        charger.getStatus.side_effect = AttributeError
        mock.return_value = charger
        yield charger


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.openevse.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain="openevse",
        data={CONF_HOST: "192.168.1.100"},
        unique_id="192.168.1.100",
    )
