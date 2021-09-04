"""Support for APCUPSd sensors."""
from __future__ import annotations

import logging

from apcaccess.status import ALL_UNITS
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_RESOURCES,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = "UPS "
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="alarmdel",
        name="Alarm Delay",
        native_unit_of_measurement=None,
        icon="mdi:alarm",
        device_class=None,
    ),
    SensorEntityDescription(
        key="ambtemp",
        name="Ambient Temperature",
        native_unit_of_measurement=None,
        icon="mdi:thermometer",
        device_class=None,
    ),
    SensorEntityDescription(
        key="apc",
        name="Status Data",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="apcmodel",
        name="Model",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="badbatts",
        name="Bad Batteries",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="battdate",
        name="Battery Replaced",
        native_unit_of_measurement=None,
        icon="mdi:calendar-clock",
        device_class=None,
    ),
    SensorEntityDescription(
        key="battstat",
        name="Battery Status",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="battv",
        name="Battery Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="bcharge",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
        device_class=None,
    ),
    SensorEntityDescription(
        key="cable",
        name="Cable Type",
        native_unit_of_measurement=None,
        icon="mdi:ethernet-cable",
        device_class=None,
    ),
    SensorEntityDescription(
        key="cumonbatt",
        name="Total Time on Battery",
        native_unit_of_measurement=None,
        icon="mdi:timer-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="date",
        name="Status Date",
        native_unit_of_measurement=None,
        icon="mdi:calendar-clock",
        device_class=None,
    ),
    SensorEntityDescription(
        key="dipsw",
        name="Dip Switch Settings",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="dlowbatt",
        name="Low Battery Signal",
        native_unit_of_measurement=None,
        icon="mdi:clock-alert",
        device_class=None,
    ),
    SensorEntityDescription(
        key="driver",
        name="Driver",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="dshutd",
        name="Shutdown Delay",
        native_unit_of_measurement=None,
        icon="mdi:timer-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="dwake",
        name="Wake Delay",
        native_unit_of_measurement=None,
        icon="mdi:timer-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="endapc",
        name="Date and Time",
        native_unit_of_measurement=None,
        icon="mdi:calendar-clock",
        device_class=None,
    ),
    SensorEntityDescription(
        key="extbatts",
        name="External Batteries",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="firmware",
        name="Firmware Version",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="hitrans",
        name="Transfer High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="hostname",
        name="Hostname",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Ambient Humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        device_class=None,
    ),
    SensorEntityDescription(
        key="itemp",
        name="Internal Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="lastxfer",
        name="Last Transfer",
        native_unit_of_measurement=None,
        icon="mdi:transfer",
        device_class=None,
    ),
    SensorEntityDescription(
        key="linefail",
        name="Input Voltage Status",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="linefreq",
        name="Line Frequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="linev",
        name="Input Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="loadpct",
        name="Load",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
        device_class=None,
    ),
    SensorEntityDescription(
        key="loadapnt",
        name="Load Apparent Power",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
        device_class=None,
    ),
    SensorEntityDescription(
        key="lotrans",
        name="Transfer Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="mandate",
        name="Manufacture Date",
        native_unit_of_measurement=None,
        icon="mdi:calendar",
        device_class=None,
    ),
    SensorEntityDescription(
        key="masterupd",
        name="Master Update",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="maxlinev",
        name="Input Voltage High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="maxtime",
        name="Battery Timeout",
        native_unit_of_measurement=None,
        icon="mdi:timer-off-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="mbattchg",
        name="Battery Shutdown",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
        device_class=None,
    ),
    SensorEntityDescription(
        key="minlinev",
        name="Input Voltage Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="mintimel",
        name="Shutdown Time",
        native_unit_of_measurement=None,
        icon="mdi:timer-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="model",
        name="Model",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="nombattv",
        name="Battery Nominal Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="nominv",
        name="Nominal Input Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="nomoutv",
        name="Nominal Output Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="nompower",
        name="Nominal Output Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="nomapnt",
        name="Nominal Apparent Power",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="numxfers",
        name="Transfer Count",
        native_unit_of_measurement=None,
        icon="mdi:counter",
        device_class=None,
    ),
    SensorEntityDescription(
        key="outcurnt",
        name="Output Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="outputv",
        name="Output Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
        device_class=None,
    ),
    SensorEntityDescription(
        key="reg1",
        name="Register 1 Fault",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="reg2",
        name="Register 2 Fault",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="reg3",
        name="Register 3 Fault",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="retpct",
        name="Restore Requirement",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
        device_class=None,
    ),
    SensorEntityDescription(
        key="selftest",
        name="Last Self Test",
        native_unit_of_measurement=None,
        icon="mdi:calendar-clock",
        device_class=None,
    ),
    SensorEntityDescription(
        key="sense",
        name="Sensitivity",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="serialno",
        name="Serial Number",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="starttime",
        name="Startup Time",
        native_unit_of_measurement=None,
        icon="mdi:calendar-clock",
        device_class=None,
    ),
    SensorEntityDescription(
        key="statflag",
        name="Status Flag",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="status",
        name="Status",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="stesti",
        name="Self Test Interval",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="timeleft",
        name="Time Left",
        native_unit_of_measurement=None,
        icon="mdi:clock-alert",
        device_class=None,
    ),
    SensorEntityDescription(
        key="tonbatt",
        name="Time on Battery",
        native_unit_of_measurement=None,
        icon="mdi:timer-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="upsmode",
        name="Mode",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="upsname",
        name="Name",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="version",
        name="Daemon Info",
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
        device_class=None,
    ),
    SensorEntityDescription(
        key="xoffbat",
        name="Transfer from Battery",
        native_unit_of_measurement=None,
        icon="mdi:transfer",
        device_class=None,
    ),
    SensorEntityDescription(
        key="xoffbatt",
        name="Transfer from Battery",
        native_unit_of_measurement=None,
        icon="mdi:transfer",
        device_class=None,
    ),
    SensorEntityDescription(
        key="xonbatt",
        name="Transfer to Battery",
        native_unit_of_measurement=None,
        icon="mdi:transfer",
        device_class=None,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

SPECIFIC_UNITS = {"ITEMP": TEMP_CELSIUS}
INFERRED_UNITS = {
    " Minutes": TIME_MINUTES,
    " Seconds": TIME_SECONDS,
    " Percent": PERCENTAGE,
    " Volts": ELECTRIC_POTENTIAL_VOLT,
    " Ampere": ELECTRIC_CURRENT_AMPERE,
    " Volt-Ampere": POWER_VOLT_AMPERE,
    " Watts": POWER_WATT,
    " Hz": FREQUENCY_HERTZ,
    " C": TEMP_CELSIUS,
    " Percent Load Capacity": PERCENTAGE,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the APCUPSd sensors."""
    apcups_data = hass.data[DOMAIN]
    resources = config[CONF_RESOURCES]

    for resource in resources:
        if resource.upper() not in apcups_data.status:
            _LOGGER.warning(
                "Sensor type: %s does not appear in the APCUPSd status output",
                resource,
            )

    entities = [
        APCUPSdSensor(apcups_data, description)
        for description in SENSOR_TYPES
        if description.key in resources
    ]

    add_entities(entities, True)


def infer_unit(value):
    """If the value ends with any of the units from ALL_UNITS.

    Split the unit off the end of the value and return the value, unit tuple
    pair. Else return the original value and None as the unit.
    """

    for unit in ALL_UNITS:
        if value.endswith(unit):
            return value[: -len(unit)], INFERRED_UNITS.get(unit, unit.strip())
    return value, None


class APCUPSdSensor(SensorEntity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(self, data, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._data = data
        self._attr_name = f"{SENSOR_PREFIX}{description.name}"

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        key = self.entity_description.key.upper()
        if key not in self._data.status:
            self._attr_native_value = None
        else:
            self._attr_native_value, inferred_unit = infer_unit(self._data.status[key])
            if not self.native_unit_of_measurement:
                self._attr_native_unit_of_measurement = inferred_unit
