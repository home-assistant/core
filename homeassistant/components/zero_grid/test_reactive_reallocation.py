"""Test reactive power reallocation functionality."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from . import (
    CONFIG,
    PLAN,
    STATE,
    calculate_effective_available_power,
    check_consumption_variance_and_reallocate,
)
from .config import ControllableLoadConfig
from .state import ControllableLoadPlanState, ControllableLoadState


class TestReactivePowerReallocation:
    """Test reactive power reallocation features."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset global state
        CONFIG.__dict__.clear()
        STATE.__dict__.clear()
        PLAN.__dict__.clear()

        # Configure test setup
        CONFIG.enable_reactive_reallocation = True
        CONFIG.variance_detection_threshold = 1.0
        CONFIG.variance_detection_delay_seconds = 30
        CONFIG.max_house_load_amps = 32
        CONFIG.hysteresis_amps = 2
        CONFIG.house_consumption_amps_entity = "sensor.house_consumption"
        CONFIG.mains_voltage_entity = "sensor.mains_voltage"
        CONFIG.allow_grid_import = True
        CONFIG.allow_solar_consumption = True

        # Set up mock loads
        CONFIG.controllable_loads = {}

        # High priority load - hot water heater
        hw_config = ControllableLoadConfig()
        hw_config.name = "hot_water"
        hw_config.priority = 0
        hw_config.max_controllable_load_amps = 10
        hw_config.min_controllable_load_amps = 10
        hw_config.load_amps_entity = "sensor.hw_current"
        hw_config.switch_entity = "switch.hot_water"
        CONFIG.controllable_loads["hot_water"] = hw_config

        # Lower priority load - EV charger
        ev_config = ControllableLoadConfig()
        ev_config.name = "ev_charger"
        ev_config.priority = 1
        ev_config.max_controllable_load_amps = 16
        ev_config.min_controllable_load_amps = 6
        ev_config.can_throttle = True
        ev_config.throttle_amps_entity = "number.ev_current"
        ev_config.load_amps_entity = "sensor.ev_current"
        ev_config.switch_entity = "switch.ev_charger"
        CONFIG.controllable_loads["ev_charger"] = ev_config

        # Initialize state
        STATE.house_consumption_amps = 15.0
        STATE.mains_voltage = 230.0
        STATE.solar_generation_kw = 8.0  # 8kW = ~35A at 230V
        STATE.allow_grid_import = True
        STATE.controllable_loads = {}

        # Hot water state - currently on and drawing expected current
        hw_state = ControllableLoadState()
        hw_state.is_on = True
        hw_state.current_load_amps = 10.0
        hw_state.expected_load_amps = 10.0
        hw_state.last_expected_update = datetime.now() - timedelta(seconds=60)
        STATE.controllable_loads["hot_water"] = hw_state

        # EV state - currently off
        ev_state = ControllableLoadState()
        ev_state.is_on = False
        ev_state.current_load_amps = 0.0
        ev_state.expected_load_amps = 0.0
        STATE.controllable_loads["ev_charger"] = ev_state

        # Initialize plan
        PLAN.available_amps = 20.0
        PLAN.used_amps = 10.0
        PLAN.controllable_loads = {}

        # Hot water plan - currently planned to be on
        hw_plan = ControllableLoadPlanState()
        hw_plan.is_on = True
        hw_plan.expected_load_amps = 10.0
        PLAN.controllable_loads["hot_water"] = hw_plan

        # EV plan - currently planned to be off
        ev_plan = ControllableLoadPlanState()
        ev_plan.is_on = False
        ev_plan.expected_load_amps = 0.0
        PLAN.controllable_loads["ev_charger"] = ev_plan

    async def test_variance_detection_hot_water_scenario(self):
        """Test detection of hot water heater reaching temperature."""
        # Simulate hot water heater reaching temperature and reducing current draw
        hw_state = STATE.controllable_loads["hot_water"]
        hw_state.current_load_amps = (
            1.0  # Dropped from 10A to 1A (thermostat satisfied)
        )
        hw_state.consumption_variance = 9.0  # Should be detected as significant

        # Mock hass for service calls
        hass = Mock()
        hass.services = Mock()
        hass.states = Mock()

        # Mock recalculate_load_control to track if it gets called
        with pytest.mock.patch(
            "homeassistant.components.zero_grid.recalculate_load_control"
        ) as mock_recalc:
            mock_recalc.return_value = AsyncMock()

            # Check variance and see if reallocation is triggered
            await check_consumption_variance_and_reallocate(hass)

            # Should trigger recalculation due to significant variance
            mock_recalc.assert_called_once_with(hass)

    async def test_effective_available_power_calculation(self):
        """Test calculation of effective available power including reactive power."""
        # Set up scenario where hot water is using less than expected
        hw_state = STATE.controllable_loads["hot_water"]
        hw_state.current_load_amps = 2.0  # Using 2A instead of 10A
        hw_state.expected_load_amps = 10.0
        hw_state.consumption_variance = 8.0  # 8A unused

        # Hot water is planned to be on
        hw_plan = PLAN.controllable_loads["hot_water"]
        hw_plan.is_on = True
        hw_plan.expected_load_amps = 10.0

        # Calculate effective available power
        effective_power = await calculate_effective_available_power()

        # Should include base available power plus reactive power from hot water variance
        # Base: 35A (solar) - 15A (house) - 2A (safety) = 18A
        # Reactive: 8A (hot water variance)
        # Total: 18A + 8A = 26A
        expected_power = 26.0
        assert abs(effective_power - expected_power) < 0.1, (
            f"Expected {expected_power}A, got {effective_power}A"
        )

    async def test_no_variance_detection_when_disabled(self):
        """Test that variance detection doesn't trigger when disabled."""
        # Disable reactive reallocation
        CONFIG.enable_reactive_reallocation = False

        # Set up significant variance
        hw_state = STATE.controllable_loads["hot_water"]
        hw_state.current_load_amps = 1.0
        hw_state.expected_load_amps = 10.0
        hw_state.consumption_variance = 9.0

        # Mock hass
        hass = Mock()

        # Mock recalculate_load_control
        with pytest.mock.patch(
            "homeassistant.components.zero_grid.recalculate_load_control"
        ) as mock_recalc:
            await check_consumption_variance_and_reallocate(hass)

            # Should NOT trigger recalculation when disabled
            mock_recalc.assert_not_called()

    async def test_variance_below_threshold_ignored(self):
        """Test that small variances below threshold are ignored."""
        # Set up small variance below threshold
        hw_state = STATE.controllable_loads["hot_water"]
        hw_state.current_load_amps = 9.5  # Only 0.5A variance
        hw_state.expected_load_amps = 10.0
        hw_state.consumption_variance = 0.5  # Below 1.0A threshold

        # Mock hass
        hass = Mock()

        # Mock recalculate_load_control
        with pytest.mock.patch(
            "homeassistant.components.zero_grid.recalculate_load_control"
        ) as mock_recalc:
            await check_consumption_variance_and_reallocate(hass)

            # Should NOT trigger recalculation for small variance
            mock_recalc.assert_not_called()

    async def test_multiple_load_variance_accumulation(self):
        """Test that variances from multiple loads are accumulated correctly."""
        # Set up variance in both loads
        hw_state = STATE.controllable_loads["hot_water"]
        hw_state.current_load_amps = 2.0  # 8A variance
        hw_state.expected_load_amps = 10.0
        hw_state.consumption_variance = 8.0

        # Add EV charger with variance too
        ev_state = STATE.controllable_loads["ev_charger"]
        ev_state.is_on = True
        ev_state.current_load_amps = 4.0  # Using 4A instead of 12A
        ev_state.expected_load_amps = 12.0
        ev_state.consumption_variance = 8.0  # Another 8A unused
        ev_state.last_expected_update = datetime.now() - timedelta(seconds=60)

        # EV plan should be on
        ev_plan = PLAN.controllable_loads["ev_charger"]
        ev_plan.is_on = True
        ev_plan.expected_load_amps = 12.0

        # Calculate effective available power
        effective_power = await calculate_effective_available_power()

        # Should include base power plus both variances
        # Base: 35A (solar) - 15A (house) - 2A (safety) = 18A
        # Reactive: 8A (hot water) + 8A (EV) = 16A
        # Total: 18A + 16A = 34A
        expected_power = 34.0
        assert abs(effective_power - expected_power) < 0.1, (
            f"Expected {expected_power}A, got {effective_power}A"
        )


if __name__ == "__main__":
    # Run basic test
    test = TestReactivePowerReallocation()
    test.setup_method()

    # Testing reactive power reallocation...

    # Test basic variance detection
    # Setup complete

    # Test effective power calculation
    import asyncio

    power = asyncio.run(test.test_effective_available_power_calculation())
    # Effective power calculation test passed

    # All basic tests passed! Reactive reallocation implementation is working.
