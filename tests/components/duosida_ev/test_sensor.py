"""Test Duosida EV sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant


async def test_sensor_state_values(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test sensor states are correct."""
    # Check status sensor
    status_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_status")
    assert status_sensor is not None
    # conn_status 2 = "Charging"
    assert status_sensor.state == "Charging"

    # Check voltage sensor
    voltage_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_voltage")
    assert voltage_sensor is not None
    assert voltage_sensor.state == "230.0"
    assert (
        voltage_sensor.attributes["unit_of_measurement"] == UnitOfElectricPotential.VOLT
    )

    # Check current sensor
    current_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_current")
    assert current_sensor is not None
    assert current_sensor.state == "16.0"
    assert (
        current_sensor.attributes["unit_of_measurement"] == UnitOfElectricCurrent.AMPERE
    )

    # Check power sensor
    power_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_power")
    assert power_sensor is not None
    assert power_sensor.state == "11040"
    assert power_sensor.attributes["unit_of_measurement"] == UnitOfPower.WATT

    # Check temperature sensor
    temp_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_temperature")
    assert temp_sensor is not None
    assert temp_sensor.state == "35.0"
    assert temp_sensor.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


async def test_sensor_cp_voltage(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test CP voltage sensor."""
    cp_voltage_sensor = hass.states.get(
        "sensor.duosida_ev_charger_192_168_1_100_cp_voltage"
    )
    assert cp_voltage_sensor is not None
    assert cp_voltage_sensor.state == "6.0"  # 6V = charging state
    assert (
        cp_voltage_sensor.attributes["unit_of_measurement"]
        == UnitOfElectricPotential.VOLT
    )


async def test_sensor_session_energy(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test session energy sensor."""
    session_energy_sensor = hass.states.get(
        "sensor.duosida_ev_charger_192_168_1_100_session_energy"
    )
    assert session_energy_sensor is not None
    assert session_energy_sensor.state == "5.5"  # From MOCK_CHARGER_STATUS
    assert (
        session_energy_sensor.attributes["unit_of_measurement"]
        == UnitOfEnergy.KILO_WATT_HOUR
    )
    # Session energy is cumulative within a session, so it's total_increasing
    assert session_energy_sensor.attributes["state_class"] == "total_increasing"


async def test_sensor_session_time(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test session time sensor converts minutes to hours."""
    session_time_sensor = hass.states.get(
        "sensor.duosida_ev_charger_192_168_1_100_session_time"
    )
    assert session_time_sensor is not None
    # 120 minutes = 2.0 hours
    assert session_time_sensor.state == "2.0"
    assert session_time_sensor.attributes["unit_of_measurement"] == UnitOfTime.HOURS


async def test_sensor_total_energy(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test total energy sensor (integrated value)."""
    total_energy_sensor = hass.states.get(
        "sensor.duosida_ev_charger_192_168_1_100_total_energy"
    )
    assert total_energy_sensor is not None
    assert (
        total_energy_sensor.attributes["unit_of_measurement"]
        == UnitOfEnergy.KILO_WATT_HOUR
    )
    # Should be TOTAL_INCREASING for HA Energy Dashboard
    assert total_energy_sensor.attributes["state_class"] == "total_increasing"


async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test some sensors are disabled by default."""
    # L2/L3 voltage sensors should be disabled by default
    voltage_l2_sensor = hass.states.get(
        "sensor.duosida_ev_charger_192_168_1_100_voltage_l2"
    )
    assert voltage_l2_sensor is None  # Disabled by default

    # Model, manufacturer, firmware should be disabled by default
    model_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_model")
    assert model_sensor is None  # Disabled by default


async def test_sensor_status_mapping(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test status sensor correctly maps status codes."""
    # Test default status (conn_status 2 = "Charging")
    status_sensor = hass.states.get("sensor.duosida_ev_charger_192_168_1_100_status")
    assert status_sensor is not None
    assert status_sensor.state == "Charging"
