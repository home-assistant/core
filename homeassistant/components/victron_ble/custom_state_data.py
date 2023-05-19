"""Custom state data for victron-ble. See https://github.com/Bluetooth-Devices/sensor-state-data/pull/47."""

import sensor_state_data
import sensor_state_data.enum


class SensorDeviceClass(sensor_state_data.BaseDeviceClass):
    """Custom class to support victron-ble specific device classes."""

    # inherited fields

    BATTERY = sensor_state_data.DeviceClass.BATTERY
    CURRENT = sensor_state_data.DeviceClass.CURRENT
    DURATION = sensor_state_data.DeviceClass.DURATION
    ENERGY = sensor_state_data.DeviceClass.ENERGY
    POWER = sensor_state_data.DeviceClass.POWER
    TEMPERATURE = sensor_state_data.DeviceClass.TEMPERATURE
    VOLTAGE = sensor_state_data.DeviceClass.VOLTAGE

    # new fields

    CURRENT_FLOW = "current_flow"


class Units(sensor_state_data.enum.StrEnum):
    """Custom class to support victron-ble specific units."""

    # inherited fields

    ELECTRIC_CURRENT_AMPERE = sensor_state_data.Units.ELECTRIC_CURRENT_AMPERE
    ELECTRIC_POTENTIAL_VOLT = sensor_state_data.Units.ELECTRIC_POTENTIAL_VOLT
    ENERGY_WATT_HOUR = sensor_state_data.Units.ENERGY_WATT_HOUR
    PERCENTAGE = sensor_state_data.Units.PERCENTAGE
    POWER_WATT = sensor_state_data.Units.POWER_WATT
    TEMP_CELSIUS = sensor_state_data.Units.TEMP_CELSIUS
    TIME_MINUTES = sensor_state_data.Units.TIME_MINUTES

    # new fields

    ELECTRIC_CURRENT_FLOW_AMPERE_HOUR = "Ah"
