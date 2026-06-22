"""Tests for the Bosch SHC sensor platform."""

from homeassistant.components.bosch_shc.sensor import (
    ENERGY_SENSOR,
    POWER_SENSOR,
    SENSOR_DESCRIPTIONS,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower


def test_power_sensor_description_has_state_class() -> None:
    """Test that the power sensor description includes state_class MEASUREMENT.

    Without state_class the HA recorder skips the entity in _get_sensor_states
    and never compiles long-term statistics for it.  That means the sensor does
    not appear in the Energy Dashboard "Individual Devices" power-rate picker
    (unit_class='power') and cannot be linked to an individual device entry.

    Regression test for GitHub issue home-assistant/core#167569.
    """
    desc = SENSOR_DESCRIPTIONS[POWER_SENSOR]
    assert desc.device_class == SensorDeviceClass.POWER
    assert desc.state_class == SensorStateClass.MEASUREMENT
    assert desc.native_unit_of_measurement == UnitOfPower.WATT


def test_energy_sensor_description_state_class_and_unit() -> None:
    """Test that the energy sensor description has the attributes required by
    the Energy Dashboard Individual Devices picker (unit_class='energy').

    The picker filters statistics by unit_class.  For kWh sensors with
    device_class ENERGY and state_class TOTAL_INCREASING the recorder produces
    statistics with unit_class='energy', which is what the picker expects.
    """
    desc = SENSOR_DESCRIPTIONS[ENERGY_SENSOR]
    assert desc.device_class == SensorDeviceClass.ENERGY
    assert desc.state_class == SensorStateClass.TOTAL_INCREASING
    assert desc.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR


def test_energy_sensor_value_fn_handles_none() -> None:
    """The energy value_fn must not raise when the device reports no value.

    A missing energyconsumption would otherwise raise TypeError (None / 1000.0)
    and take the entity unavailable; the guard returns None instead.
    """
    desc = SENSOR_DESCRIPTIONS[ENERGY_SENSOR]

    class _Dev:
        energyconsumption = None

    assert desc.value_fn(_Dev()) is None

    class _Dev2:
        energyconsumption = 2500.0

    assert desc.value_fn(_Dev2()) == 2.5
