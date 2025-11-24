"""Test Duosida EV sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_sensor_entities_created(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test that sensor entities are created."""
    entity_registry = er.async_get(hass)

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "duosida_ev"
    ]

    assert len(entries) > 0


async def test_sensor_state_values(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test sensor states are correct."""
    entity_registry = er.async_get(hass)

    status_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_state"
    )

    if status_entry:
        status_sensor = hass.states.get(status_entry)
        assert status_sensor is not None
        # conn_status 2 = "charging" (lowercase for ENUM)
        assert status_sensor.state == "charging"


async def test_sensor_voltage(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test voltage sensor."""
    entity_registry = er.async_get(hass)

    voltage_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_voltage"
    )

    if voltage_entry:
        voltage_sensor = hass.states.get(voltage_entry)
        assert voltage_sensor is not None
        assert voltage_sensor.state == "230.0"
        assert (
            voltage_sensor.attributes["unit_of_measurement"]
            == UnitOfElectricPotential.VOLT
        )


async def test_sensor_current(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test current sensor."""
    entity_registry = er.async_get(hass)

    current_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_current"
    )

    if current_entry:
        current_sensor = hass.states.get(current_entry)
        assert current_sensor is not None
        assert current_sensor.state == "16.0"
        assert (
            current_sensor.attributes["unit_of_measurement"]
            == UnitOfElectricCurrent.AMPERE
        )


async def test_sensor_power(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test power sensor."""
    entity_registry = er.async_get(hass)

    power_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_power"
    )

    if power_entry:
        power_sensor = hass.states.get(power_entry)
        assert power_sensor is not None
        assert power_sensor.state == "11040"
        assert power_sensor.attributes["unit_of_measurement"] == UnitOfPower.WATT


async def test_sensor_temperature(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test temperature sensor."""
    entity_registry = er.async_get(hass)

    temp_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_temperature"
    )

    if temp_entry:
        temp_sensor = hass.states.get(temp_entry)
        assert temp_sensor is not None
        assert temp_sensor.state == "35.0"
        assert (
            temp_sensor.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
        )


async def test_sensor_cp_voltage(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test CP voltage sensor."""
    entity_registry = er.async_get(hass)

    cp_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_cp_voltage"
    )

    if cp_entry:
        cp_sensor = hass.states.get(cp_entry)
        assert cp_sensor is not None
        assert cp_sensor.state == "6.0"
        assert (
            cp_sensor.attributes["unit_of_measurement"] == UnitOfElectricPotential.VOLT
        )


async def test_sensor_session_energy(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test session energy sensor."""
    entity_registry = er.async_get(hass)

    session_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_session_energy"
    )

    if session_entry:
        session_sensor = hass.states.get(session_entry)
        assert session_sensor is not None
        assert session_sensor.state == "5.5"
        assert (
            session_sensor.attributes["unit_of_measurement"]
            == UnitOfEnergy.KILO_WATT_HOUR
        )
        assert session_sensor.attributes["state_class"] == "total_increasing"


async def test_sensor_session_time(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test session time sensor converts minutes to hours."""
    entity_registry = er.async_get(hass)

    time_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_session_time"
    )

    if time_entry:
        time_sensor = hass.states.get(time_entry)
        assert time_sensor is not None
        # 120 minutes = 2.0 hours
        assert time_sensor.state == "2.0"
        assert time_sensor.attributes["unit_of_measurement"] == UnitOfTime.HOURS


async def test_sensor_total_energy(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test total energy sensor (integrated value)."""
    entity_registry = er.async_get(hass)

    total_entry = entity_registry.async_get_entity_id(
        "sensor", "duosida_ev", "03123456789012345678_total_energy"
    )

    if total_entry:
        total_sensor = hass.states.get(total_entry)
        assert total_sensor is not None
        assert (
            total_sensor.attributes["unit_of_measurement"]
            == UnitOfEnergy.KILO_WATT_HOUR
        )
        assert total_sensor.attributes["state_class"] == "total_increasing"


async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    setup_integration: Any,
) -> None:
    """Test some sensors are disabled by default."""
    entity_registry = er.async_get(hass)

    # L2/L3 voltage sensors should be disabled by default
    voltage_l2_entry = entity_registry.async_get(
        "sensor.03123456789012345678_voltage_l2"
    )
    if voltage_l2_entry:
        assert voltage_l2_entry.disabled_by is not None


async def test_sensor_native_value_no_data(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_duosida_charger: Any,
) -> None:
    """Test sensor returns None when coordinator has no data."""
    from homeassistant.components.duosida_ev.coordinator import (
        DuosidaDataUpdateCoordinator,
    )
    from homeassistant.components.duosida_ev.sensor import SENSORS, DuosidaSensor

    from .conftest import MockDuosidaCharger

    mock_charger = MockDuosidaCharger(
        host="192.168.1.100",
        port=9988,
        device_id="03123456789012345678",
    )

    with (
        patch(
            "homeassistant.components.duosida_ev.coordinator.Store.async_load",
            return_value=None,
        ),
        patch(
            "homeassistant.components.duosida_ev.coordinator.Store.async_save",
            return_value=None,
        ),
    ):
        coordinator = DuosidaDataUpdateCoordinator(
            hass,
            mock_charger,
            device_id="03123456789012345678",
        )

        # Create sensor without refreshing coordinator (so data is None)
        sensor = DuosidaSensor(
            coordinator,
            "03123456789012345678",
            SENSORS[0],  # State sensor
        )

        # Data should be None, so native_value should return None
        assert coordinator.data is None
        assert sensor.native_value is None
