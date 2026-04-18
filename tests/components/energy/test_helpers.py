"""Test the Energy helpers."""

import pytest

from homeassistant.components.energy.helpers import (
    generate_power_sensor_entity_id,
    generate_power_sensor_unique_id,
)


def test_generate_power_sensor_unique_id_inverted() -> None:
    """Test unique ID generation for inverted power config."""
    config = {"stat_rate_inverted": "sensor.battery_power"}
    unique_id = generate_power_sensor_unique_id("battery", config)
    assert unique_id == "energy_power_battery_inverted_sensor_battery_power"


def test_generate_power_sensor_unique_id_combined() -> None:
    """Test unique ID generation for combined power config."""
    config = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }
    unique_id = generate_power_sensor_unique_id("battery", config)
    assert (
        unique_id
        == "energy_power_battery_combined_sensor_battery_discharge_sensor_battery_charge"
    )


def test_generate_power_sensor_unique_id_standard() -> None:
    """Test unique ID generation raises for standard config (schema-invalid)."""
    config = {"stat_rate": "sensor.battery_power"}
    with pytest.raises(RuntimeError, match="Invalid power config"):
        generate_power_sensor_unique_id("battery", config)


def test_generate_power_sensor_unique_id_empty() -> None:
    """Test unique ID generation raises for empty config (schema-invalid)."""
    config = {}
    with pytest.raises(RuntimeError, match="Invalid power config"):
        generate_power_sensor_unique_id("battery", config)


def test_generate_power_sensor_unique_id_grid() -> None:
    """Test unique ID generation for grid source type."""
    config = {"stat_rate_inverted": "sensor.grid_power"}
    unique_id = generate_power_sensor_unique_id("grid", config)
    assert unique_id == "energy_power_grid_inverted_sensor_grid_power"


def test_generate_power_sensor_entity_id_inverted_with_prefix() -> None:
    """Test entity ID generation for inverted config with sensor prefix."""
    config = {"stat_rate_inverted": "sensor.battery_power"}
    entity_id = generate_power_sensor_entity_id("battery", config)
    assert entity_id == "sensor.battery_power_inverted"


def test_generate_power_sensor_entity_id_inverted_without_prefix() -> None:
    """Test entity ID generation for inverted config without sensor prefix."""
    config = {"stat_rate_inverted": "custom.battery_power"}
    entity_id = generate_power_sensor_entity_id("battery", config)
    assert entity_id == "sensor.custom_battery_power_inverted"


def test_generate_power_sensor_entity_id_combined() -> None:
    """Test entity ID generation for combined power config."""
    config = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }
    entity_id = generate_power_sensor_entity_id("battery", config)
    assert (
        entity_id == "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )


def test_generate_power_sensor_entity_id_combined_without_prefix() -> None:
    """Test entity ID generation for combined config without sensor prefix."""
    config = {
        "stat_rate_from": "battery_discharge",
        "stat_rate_to": "battery_charge",
    }
    entity_id = generate_power_sensor_entity_id("battery", config)
    assert (
        entity_id == "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )


def test_generate_power_sensor_entity_id_standard() -> None:
    """Test entity ID generation raises for standard config (schema-invalid)."""
    config = {"stat_rate": "sensor.battery_power"}
    with pytest.raises(RuntimeError, match="Invalid power config"):
        generate_power_sensor_entity_id("battery", config)


def test_generate_power_sensor_entity_id_empty() -> None:
    """Test entity ID generation raises for empty config (schema-invalid)."""
    config = {}
    with pytest.raises(RuntimeError, match="Invalid power config"):
        generate_power_sensor_entity_id("battery", config)


def test_generate_power_sensor_entity_id_grid() -> None:
    """Test entity ID generation for grid source type."""
    config = {
        "stat_rate_from": "sensor.grid_import",
        "stat_rate_to": "sensor.grid_export",
    }
    entity_id = generate_power_sensor_entity_id("grid", config)
    assert entity_id == "sensor.energy_grid_grid_import_grid_export_net_power"
