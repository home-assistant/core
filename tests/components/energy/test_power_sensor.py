"""Tests for EnergyPowerSensor."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.energy import async_get_manager
from homeassistant.components.energy.sensor import EnergyPowerSensor, SensorManager
from homeassistant.components.recorder import Recorder
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_power_sensor_inverted_initialization(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor initialization with inverted config."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="energy_power_battery_inv_sensor_battery_power",
        entity_id="sensor.battery_power_inverted",
    )

    assert sensor._is_inverted is True
    assert sensor._is_combined is False
    assert sensor._source_sensors == ["sensor.battery_power"]
    assert sensor._attr_unique_id == "energy_power_battery_inv_sensor_battery_power"
    assert sensor.entity_id == "sensor.battery_power_inverted"
    assert sensor._attr_device_class == SensorDeviceClass.POWER
    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
    assert sensor._attr_should_poll is False


async def test_power_sensor_combined_initialization(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor initialization with combined config."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="energy_power_battery_combined_sensor_battery_discharge_sensor_battery_charge",
        entity_id="sensor.energy_battery_battery_discharge_power",
    )

    assert sensor._is_inverted is False
    assert sensor._is_combined is True
    assert sensor._source_sensors == [
        "sensor.battery_discharge",
        "sensor.battery_charge",
    ]


async def test_power_sensor_inverted_state_update(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor inverted mode state updates."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Set up source sensor with positive value
    hass.states.async_set(
        "sensor.battery_power",
        "100.5",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value == -100.5


async def test_power_sensor_inverted_negative_value(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor inverted mode with negative source value."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Set up source sensor with negative value (should become positive)
    hass.states.async_set("sensor.battery_power", "-50.0")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value == 50.0


async def test_power_sensor_combined_state_update(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor combined mode state updates."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Set up source sensors
    hass.states.async_set(
        "sensor.battery_discharge",
        "150.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    sensor._update_state()
    # Result = discharge - charge = 150 - 50 = 100
    assert sensor._attr_native_value == 100.0


async def test_power_sensor_combined_net_charging(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor combined mode when net charging (negative result)."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Set up source sensors - more charging than discharging
    hass.states.async_set("sensor.battery_discharge", "30.0")
    hass.states.async_set("sensor.battery_charge", "80.0")
    await hass.async_block_till_done()

    sensor._update_state()
    # Result = 30 - 80 = -50 (net charging)
    assert sensor._attr_native_value == -50.0


async def test_power_sensor_inverted_unknown_state(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor inverted mode with unknown source state."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    hass.states.async_set("sensor.battery_power", "unknown")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_inverted_unavailable_state(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor inverted mode with unavailable source state."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    hass.states.async_set("sensor.battery_power", "unavailable")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_inverted_missing_source(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor inverted mode with missing source sensor."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.nonexistent"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Don't create the source sensor - it doesn't exist
    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_inverted_non_numeric_state(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor inverted mode with non-numeric source state."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    hass.states.async_set("sensor.battery_power", "not_a_number")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_combined_one_unknown(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor combined mode with one unknown source."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    hass.states.async_set("sensor.battery_discharge", "100.0")
    hass.states.async_set("sensor.battery_charge", "unknown")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_combined_one_unavailable(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor combined mode with one unavailable source."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    hass.states.async_set("sensor.battery_discharge", "unavailable")
    hass.states.async_set("sensor.battery_charge", "50.0")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_combined_one_missing(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor combined mode with one missing source."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Only set one sensor
    hass.states.async_set("sensor.battery_discharge", "100.0")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_combined_non_numeric(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor combined mode with non-numeric source state."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    hass.states.async_set("sensor.battery_discharge", "100.0")
    hass.states.async_set("sensor.battery_charge", "invalid")
    await hass.async_block_till_done()

    sensor._update_state()
    assert sensor._attr_native_value is None


async def test_power_sensor_async_added_to_hass_inverted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test EnergyPowerSensor async_added_to_hass for inverted mode."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Register source sensor in entity registry with unit
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_power",
        suggested_object_id="battery_power",
        unit_of_measurement=UnitOfPower.WATT,
        original_name="Battery Power",
    )

    # Set up source sensor state
    hass.states.async_set(
        "sensor.battery_power",
        "100.0",
        {"friendly_name": "Battery Power"},
    )
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()

    assert sensor._attr_name == "Battery Power Inverted"
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
    assert sensor._attr_native_value == -100.0


async def test_power_sensor_async_added_to_hass_inverted_no_source(
    hass: HomeAssistant,
) -> None:
    """Test EnergyPowerSensor async_added_to_hass when source doesn't exist."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Don't set up source sensor - name should be generated from entity_id
    await sensor.async_added_to_hass()

    assert sensor._attr_name == "Battery Power Inverted"


async def test_power_sensor_async_added_to_hass_combined(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test EnergyPowerSensor async_added_to_hass for combined mode."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Register first source sensor in entity registry with unit
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_discharge",
        suggested_object_id="battery_discharge",
        unit_of_measurement=UnitOfPower.KILO_WATT,
    )

    # Set up source sensor states with units
    hass.states.async_set(
        "sensor.battery_discharge",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "30.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()

    assert sensor._attr_name == "Battery Power"
    # Combined mode always uses Watts
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
    # Both sensors in kW: 100 kW = 100,000 W, 30 kW = 30,000 W
    # Result: 100,000 - 30,000 = 70,000 W
    assert sensor._attr_native_value == 70000.0


async def test_power_sensor_copies_unit_when_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test EnergyPowerSensor copies unit even when source is unavailable."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Register source sensor in entity registry with unit and precision
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_power",
        suggested_object_id="battery_power",
        unit_of_measurement=UnitOfPower.WATT,
        capabilities={"suggested_display_precision": 1},
    )

    # Set source sensor as unavailable
    hass.states.async_set("sensor.battery_power", "unavailable")
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()

    # Unit should still be copied from registry
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.WATT


async def test_power_sensor_state_change_listener(hass: HomeAssistant) -> None:
    """Test EnergyPowerSensor updates on source state changes."""
    config: Mapping[str, Any] = {"stat_rate_inverted": "sensor.battery_power"}

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_inverted",
        entity_id="sensor.test_inverted",
    )
    sensor.hass = hass

    # Set up source sensor
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()
    assert sensor._attr_native_value == -100.0

    # Update source sensor - should trigger listener
    hass.states.async_set("sensor.battery_power", "200.0")
    await hass.async_block_till_done()

    # Value should be updated via the state change listener
    assert sensor._attr_native_value == -200.0


async def test_power_sensor_combined_different_units_kw_w(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test combined sensors with different units (kW + W)."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Register first sensor in entity registry
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_discharge",
        suggested_object_id="battery_discharge",
        unit_of_measurement=UnitOfPower.KILO_WATT,
    )

    # Set up source sensors with different units
    hass.states.async_set(
        "sensor.battery_discharge",
        "150.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()

    # Combined mode always uses Watts
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
    # 150 kW = 150,000 W, 50 W = 50 W
    # Result: 150,000 - 50 = 149,950 W
    assert sensor._attr_native_value == 149950.0


async def test_power_sensor_combined_different_units_w_kw(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test combined sensors with different units (W + kW)."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Register first sensor in entity registry
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_discharge",
        suggested_object_id="battery_discharge",
        unit_of_measurement=UnitOfPower.WATT,
    )

    # Set up source sensors with different units
    hass.states.async_set(
        "sensor.battery_discharge",
        "150000.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()

    # Combined mode always uses Watts
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
    # 150,000 W = 150,000 W, 50 kW = 50,000 W
    # Result: 150,000 - 50,000 = 100,000 W
    assert sensor._attr_native_value == 100000.0


async def test_power_sensor_combined_same_unit_kw(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test combined sensors with same units (both kW)."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Register first sensor in entity registry
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_discharge",
        suggested_object_id="battery_discharge",
        unit_of_measurement=UnitOfPower.KILO_WATT,
    )

    # Set up source sensors both in kW
    hass.states.async_set(
        "sensor.battery_discharge",
        "150.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    await hass.async_block_till_done()

    await sensor.async_added_to_hass()

    # Combined mode always uses Watts
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
    # Both in kW: 150 kW = 150,000 W, 50 kW = 50,000 W
    # Result: 150,000 - 50,000 = 100,000 W
    assert sensor._attr_native_value == 100000.0


async def test_power_sensor_combined_missing_units(hass: HomeAssistant) -> None:
    """Test combined sensors with missing units (backwards compatibility)."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # Set up source sensors without units in state attributes
    hass.states.async_set("sensor.battery_discharge", "150.0")
    hass.states.async_set("sensor.battery_charge", "50.0")
    await hass.async_block_till_done()

    sensor._update_state()

    # Without units, values are used as-is (backwards compatibility)
    # Result: 150 - 50 = 100
    assert sensor._attr_native_value == 100.0


async def test_power_sensor_combined_one_missing_unit(hass: HomeAssistant) -> None:
    """Test combined sensors when one sensor is missing unit."""
    config: Mapping[str, Any] = {
        "stat_rate_from": "sensor.battery_discharge",
        "stat_rate_to": "sensor.battery_charge",
    }

    sensor = EnergyPowerSensor(
        source_type="battery",
        config=config,
        unique_id="test_combined",
        entity_id="sensor.test_combined",
    )
    sensor.hass = hass

    # First sensor has unit, second doesn't
    hass.states.async_set(
        "sensor.battery_discharge",
        "150.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    hass.states.async_set("sensor.battery_charge", "50.0")
    await hass.async_block_till_done()

    sensor._update_state()

    # First sensor converted: 150 kW = 150,000 W
    # Second sensor used as-is: 50
    # Result: 150,000 - 50 = 149,950
    assert sensor._attr_native_value == 149950.0


async def test_needs_power_sensor_standard(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns False for standard stat_rate."""
    assert SensorManager._needs_power_sensor({"stat_rate": "sensor.power"}) is False


async def test_needs_power_sensor_inverted(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns True for inverted config."""
    assert (
        SensorManager._needs_power_sensor({"stat_rate_inverted": "sensor.power"})
        is True
    )


async def test_needs_power_sensor_combined(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns True for combined config."""
    assert (
        SensorManager._needs_power_sensor(
            {
                "stat_rate_from": "sensor.discharge",
                "stat_rate_to": "sensor.charge",
            }
        )
        is True
    )


async def test_needs_power_sensor_partial_combined(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns False for incomplete combined config."""
    # Only stat_rate_from without stat_rate_to
    assert (
        SensorManager._needs_power_sensor({"stat_rate_from": "sensor.discharge"})
        is False
    )


async def test_power_sensor_manager_creation(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SensorManager creates power sensors correctly."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up a source sensor
    hass.states.async_set(
        "sensor.battery_power",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor entity was created
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert float(state.state) == -100.0


async def test_power_sensor_manager_cleanup(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SensorManager removes power sensors when config changes."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensors
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Create with inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify sensor exists and has a valid value
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert state.state == "-100.0"

    # Update to remove power_config (use direct stat_rate)
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "stat_rate": "sensor.battery_power",
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify sensor was removed (state becomes unavailable when entity is removed)
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is None or state.state == "unavailable"


async def test_power_sensor_grid_combined(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test power sensor for grid with combined config."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensors
    hass.states.async_set(
        "sensor.grid_import",
        "500.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.grid_export",
        "200.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with grid that has combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.grid_energy_import",
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_energy_export",
                        }
                    ],
                    "power": [
                        {
                            "power_config": {
                                "stat_rate_from": "sensor.grid_import",
                                "stat_rate_to": "sensor.grid_export",
                            }
                        }
                    ],
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor entity was created
    state = hass.states.get("sensor.energy_grid_grid_import_power")
    assert state is not None
    # 500 - 200 = 300 (net import)
    assert float(state.state) == 300.0


async def test_power_sensor_device_assignment(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test power sensor is assigned to same device as source sensor."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Create a config entry for the device
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    # Create a device and register source sensor to it
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "battery_device")},
        name="Battery Device",
    )

    # Register the source sensor with the device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_power",
        suggested_object_id="battery_power",
        device_id=device_entry.id,
    )

    # Set up source sensor state
    hass.states.async_set(
        "sensor.battery_power",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor was created and assigned to same device
    power_sensor_entry = entity_registry.async_get("sensor.battery_power_inverted")
    assert power_sensor_entry is not None
    assert power_sensor_entry.device_id == device_entry.id


async def test_power_sensor_device_assignment_combined_second_sensor(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test power sensor checks second sensor if first has no device."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Create a config entry for the device
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    # Create a device and register second sensor to it
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "battery_device")},
        name="Battery Device",
    )

    # Register first sensor WITHOUT device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_discharge",
        suggested_object_id="battery_discharge",
    )

    # Register second sensor WITH device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_charge",
        suggested_object_id="battery_charge",
        device_id=device_entry.id,
    )

    # Set up source sensor states
    hass.states.async_set(
        "sensor.battery_discharge",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor was created and assigned to second sensor's device
    power_sensor_entry = entity_registry.async_get(
        "sensor.energy_battery_battery_discharge_power"
    )
    assert power_sensor_entry is not None
    assert power_sensor_entry.device_id == device_entry.id
