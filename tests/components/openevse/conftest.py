"""Test Fixtures for the OpenEVSE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_charger() -> Generator[MagicMock]:
    """Create a mock OpenEVSE charger."""
    with (
        patch(
            "homeassistant.components.openevse.OpenEVSE",
            autospec=True,
        ) as mock,
        patch(
            "homeassistant.components.openevse.config_flow.OpenEVSE",
            new=mock,
        ),
    ):
        charger = mock.return_value
        charger.update = AsyncMock()
        charger.status = "Charging"
        charger.charge_time_elapsed = 3600  # 60 minutes in seconds
        charger.ambient_temperature = 25.5
        charger.ir_temperature = 30.2
        charger.rtc_temperature = 28.7
        charger.usage_session = 15000  # 15 kWh in Wh
        charger.usage_total = 500000  # 500 kWh in Wh
        charger.charging_current = 32.0
        yield charger


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.openevse.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.100"}, entry_id="FAKE"
    )
