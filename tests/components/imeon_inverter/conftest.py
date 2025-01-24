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
            "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.get_serial",
            return_value=TEST_SERIAL,
        ),
        patch(
            "homeassistant.components.imeon_inverter.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.imeon_inverter.coordinator.InverterCoordinator",
            autospec=True,
        ) as scale_mock,
    ):
        scale = scale_mock.return_value

        # Battery
        scale.battery_autonomy = 4.5
        scale.battery_charge_time = 120
        scale.battery_power = 2500.0
        scale.battery_soc = 78.0
        scale.battery_stored = 10.2

        # Grid
        scale.grid_current_l1 = 12.5
        scale.grid_current_l2 = 10.8
        scale.grid_current_l3 = 11.2
        scale.grid_frequency = 50.0
        scale.grid_voltage_l1 = 230.0
        scale.grid_voltage_l2 = 229.5
        scale.grid_voltage_l3 = 230.1

        # AC Input
        scale.input_power_l1 = 1000.0
        scale.input_power_l2 = 950.0
        scale.input_power_l3 = 980.0
        scale.input_power_total = 2930.0

        # Inverter settings
        scale.inverter_charging_current_limit = 50
        scale.inverter_injection_power_limit = 5000.0

        # Meter
        scale.meter_power = 2000.0
        scale.meter_power_protocol = 2018.0

        # AC Output
        scale.output_current_l1 = 15.0
        scale.output_current_l2 = 14.5
        scale.output_current_l3 = 15.2
        scale.output_frequency = 49.9
        scale.output_power_l1 = 1100.0
        scale.output_power_l2 = 1080.0
        scale.output_power_l3 = 1120.0
        scale.output_power_total = 3300.0
        scale.output_voltage_l1 = 231.0
        scale.output_voltage_l2 = 229.8
        scale.output_voltage_l3 = 230.2

        # Solar Panel
        scale.pv_consumed = 1500.0
        scale.pv_injected = 800.0
        scale.pv_power_1 = 1200.0
        scale.pv_power_2 = 1300.0
        scale.pv_power_total = 2500.0

        # Temperature
        scale.temp_air_temperature = 25.0
        scale.temp_component_temperature = 45.5

        # Monitoring (data over the last 24 hours)
        scale.monitoring_building_consumption = 3000.0
        scale.monitoring_economy_factor = 0.8
        scale.monitoring_grid_consumption = 500.0
        scale.monitoring_grid_injection = 700.0
        scale.monitoring_grid_power_flow = -200.0
        scale.monitoring_self_consumption = 85.0
        scale.monitoring_self_sufficiency = 90.0
        scale.monitoring_solar_production = 2600.0

        # Monitoring (instant minute data)
        scale.monitoring_minute_building_consumption = 50.0
        scale.monitoring_minute_grid_consumption = 8.3
        scale.monitoring_minute_grid_injection = 11.7
        scale.monitoring_minute_grid_power_flow = -3.4
        scale.monitoring_minute_solar_production = 43.3

        yield scale


@pytest.fixture
def mock_login_async_setup_entry() -> Generator[AsyncMock]:
    """Fixture for mocking login and async_setup_entry."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.get_serial",
            return_value=TEST_SERIAL,
        ),
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
