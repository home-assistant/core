"""Configuration for the Imeon Inverter integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, patch

# Sample test data
TEST_USER_INPUT = {
    CONF_ADDRESS: "192.168.200.1",
    CONF_USERNAME: "user@local",
    CONF_PASSWORD: "password",
}

TEST_SERIAL = "111111111111111"


@pytest.fixture
def mock_imeon_inverter() -> Generator[MagicMock]:
    """Mock data from the device."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.coordinator.InverterCoordinator",
            autospec=True,
        ) as inverter_mock,
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.init",
            return_value=None,
        ),
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.update",
            return_value=None,
        ),
    ):
        inverter = inverter_mock.return_value

        # Battery
        inverter.battery_autonomy = 4.5
        inverter.battery_charge_time = 120
        inverter.battery_power = 2500.0
        inverter.battery_soc = 78.0
        inverter.battery_stored = 10.2

        # Grid
        inverter.grid_current_l1 = 12.5
        inverter.grid_current_l2 = 10.8
        inverter.grid_current_l3 = 11.2
        inverter.grid_frequency = 50.0
        inverter.grid_voltage_l1 = 230.0
        inverter.grid_voltage_l2 = 229.5
        inverter.grid_voltage_l3 = 230.1

        # AC Input
        inverter.input_power_l1 = 1000.0
        inverter.input_power_l2 = 950.0
        inverter.input_power_l3 = 980.0
        inverter.input_power_total = 2930.0

        # Inverter settings
        inverter.inverter_charging_current_limit = 50
        inverter.inverter_injection_power_limit = 5000.0

        # Meter
        inverter.meter_power = 2000.0
        inverter.meter_power_protocol = 2018.0

        # AC Output
        inverter.output_current_l1 = 15.0
        inverter.output_current_l2 = 14.5
        inverter.output_current_l3 = 15.2
        inverter.output_frequency = 49.9
        inverter.output_power_l1 = 1100.0
        inverter.output_power_l2 = 1080.0
        inverter.output_power_l3 = 1120.0
        inverter.output_power_total = 3300.0
        inverter.output_voltage_l1 = 231.0
        inverter.output_voltage_l2 = 229.8
        inverter.output_voltage_l3 = 230.2

        # Solar Panel
        inverter.pv_consumed = 1500.0
        inverter.pv_injected = 800.0
        inverter.pv_power_1 = 1200.0
        inverter.pv_power_2 = 1300.0
        inverter.pv_power_total = 2500.0

        # Temperature
        inverter.temp_air_temperature = 25.0
        inverter.temp_component_temperature = 45.5

        # Monitoring (data over the last 24 hours)
        inverter.monitoring_building_consumption = 3000.0
        inverter.monitoring_economy_factor = 0.8
        inverter.monitoring_grid_consumption = 500.0
        inverter.monitoring_grid_injection = 700.0
        inverter.monitoring_grid_power_flow = -200.0
        inverter.monitoring_self_consumption = 85.0
        inverter.monitoring_self_sufficiency = 90.0
        inverter.monitoring_solar_production = 2600.0

        # Monitoring (instant minute data)
        inverter.monitoring_minute_building_consumption = 50.0
        inverter.monitoring_minute_grid_consumption = 8.3
        inverter.monitoring_minute_grid_injection = 11.7
        inverter.monitoring_minute_grid_power_flow = -3.4
        inverter.monitoring_minute_solar_production = 43.3

        yield inverter


@pytest.fixture
def mock_login() -> Generator[AsyncMock]:
    """Fixture for mocking login."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_serial() -> Generator[AsyncMock]:
    """Fixture for mocking serial."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.get_serial",
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_login_async_setup_entry() -> Generator[AsyncMock]:
    """Fixture for mocking login and async_setup_entry."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.async_setup_entry",
            return_value=True,
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=TEST_SERIAL,
    )
