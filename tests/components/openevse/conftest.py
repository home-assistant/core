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
        charger.test_and_get = AsyncMock()
        charger.test_and_get.return_value = {
            "serial": "deadbeeffeed",
            "model": "openevse_wifi_v1",
        }
        # Websocket support
        charger.ws_start = MagicMock()
        charger.ws_disconnect = AsyncMock()
        charger.websocket = MagicMock()
        charger.callback = None
        # Status sensors
        charger.status = "Charging"
        charger.vehicle = True
        charger.mode = "STA"
        charger.charge_mode = "fast"
        charger.divertmode = "normal"
        charger.manual_override = False
        charger.ota_update = "none"
        charger.service_level = "2"
        # Timing sensors
        charger.charge_time_elapsed = 3600  # 60 minutes in seconds
        charger.vehicle_eta = None
        # Electrical sensors
        charger.charging_current = 32.0
        charger.charging_voltage = 240
        charger.charging_power = 7680.0
        charger.current_power = 7680
        charger.current_capacity = 32
        charger.max_current = 48
        charger.min_amps = 6
        charger.max_amps = 48
        charger.max_current_soft = 20
        # Divert/solar mode sensors
        charger.available_current = 32.0
        charger.smoothed_available_current = 32.0
        charger.charge_rate = 32.0
        # Temperature sensors
        charger.ambient_temperature = 25.5
        charger.ir_temperature = 30.2
        charger.rtc_temperature = 28.7
        charger.esp_temperature = 45.0
        # Energy sensors
        charger.usage_session = 15000  # 15 kWh in Wh
        charger.usage_total = 500000  # 500 kWh in Wh
        charger.total_day = 10  # 10 kWh in Wh
        charger.total_week = 50  # 50 kWh in Wh
        charger.total_month = 200  # 200 kWh in Wh
        charger.total_year = 2000  # 2000 kWh in Wh
        # Vehicle sensors
        charger.vehicle_soc = 75
        charger.vehicle_range = 250
        # Connectivity sensors
        charger.wifi_signal = -65
        # Power shaper sensors
        charger.shaper_live_power = 5000
        charger.shaper_available_current = 20.0
        charger.shaper_max_power = 11000
        # Safety trip count sensors
        charger.gfi_trip_count = 0
        charger.no_gnd_trip_count = 0
        charger.stuck_relay_trip_count = 0
        # System diagnostic sensors
        charger.uptime = 86400  # 1 day in seconds
        charger.freeram = 50000
        yield charger


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.openevse.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def has_serial_number() -> bool:
    """Return a serial number."""
    return True


@pytest.fixture
def serial_number(has_serial_number: bool) -> str | None:
    """Return a serial number."""
    if has_serial_number:
        return "deadbeeffeed"
    return None


@pytest.fixture
def mock_config_entry(serial_number: str) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        title="openevse_mock_config",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        entry_id="FAKE",
        unique_id=serial_number,
    )
