"""Support for APCUPSd sensors."""
from __future__ import annotations

import logging

from apcaccess.status import ALL_UNITS
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_RESOURCES,
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
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = "UPS "
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="alarmdel",
        name="Alarm Delay",
        icon="mdi:alarm",
    ),
    SensorEntityDescription(
        key="ambtemp",
        name="Ambient Temperature",
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="apc",
        name="Status Data",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="apcmodel",
        name="Model",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="badbatts",
        name="Bad Batteries",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="battdate",
        name="Battery Replaced",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="battstat",
        name="Battery Status",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="battv",
        name="Battery Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="bcharge",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="cable",
        name="Cable Type",
        icon="mdi:ethernet-cable",
    ),
    SensorEntityDescription(
        key="cumonbatt",
        name="Total Time on Battery",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="date",
        name="Status Date",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="dipsw",
        name="Dip Switch Settings",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="dlowbatt",
        name="Low Battery Signal",
        icon="mdi:clock-alert",
    ),
    SensorEntityDescription(
        key="driver",
        name="Driver",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="dshutd",
        name="Shutdown Delay",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="dwake",
        name="Wake Delay",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="end apc",
        name="Date and Time",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="extbatts",
        name="External Batteries",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="firmware",
        name="Firmware Version",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="hitrans",
        name="Transfer High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="hostname",
        name="Hostname",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="humidity",
        name="Ambient Humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="itemp",
        name="Internal Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="lastxfer",
        name="Last Transfer",
        icon="mdi:transfer",
    ),
    SensorEntityDescription(
        key="linefail",
        name="Input Voltage Status",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="linefreq",
        name="Line Frequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="linev",
        name="Input Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="loadpct",
        name="Load",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="loadapnt",
        name="Load Apparent Power",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="lotrans",
        name="Transfer Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="mandate",
        name="Manufacture Date",
        icon="mdi:calendar",
    ),
    SensorEntityDescription(
        key="masterupd",
        name="Master Update",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="maxlinev",
        name="Input Voltage High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="maxtime",
        name="Battery Timeout",
        icon="mdi:timer-off-outline",
    ),
    SensorEntityDescription(
        key="mbattchg",
        name="Battery Shutdown",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
    ),
    SensorEntityDescription(
        key="minlinev",
        name="Input Voltage Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="mintimel",
        name="Shutdown Time",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="model",
        name="Model",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="nombattv",
        name="Battery Nominal Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="nominv",
        name="Nominal Input Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="nomoutv",
        name="Nominal Output Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="nompower",
        name="Nominal Output Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="nomapnt",
        name="Nominal Apparent Power",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="numxfers",
        name="Transfer Count",
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key="outcurnt",
        name="Output Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="outputv",
        name="Output Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="reg1",
        name="Register 1 Fault",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="reg2",
        name="Register 2 Fault",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="reg3",
        name="Register 3 Fault",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="retpct",
        name="Restore Requirement",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
    ),
    SensorEntityDescription(
        key="selftest",
        name="Last Self Test",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="sense",
        name="Sensitivity",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="serialno",
        name="Serial Number",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="starttime",
        name="Startup Time",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="statflag",
        name="Status Flag",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="status",
        name="Status",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="stesti",
        name="Self Test Interval",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="timeleft",
        name="Time Left",
        icon="mdi:clock-alert",
    ),
    SensorEntityDescription(
        key="tonbatt",
        name="Time on Battery",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="upsmode",
        name="Mode",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="upsname",
        name="Name",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="version",
        name="Daemon Info",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="xoffbat",
        name="Transfer from Battery",
        icon="mdi:transfer",
    ),
    SensorEntityDescription(
        key="xoffbatt",
        name="Transfer from Battery",
        icon="mdi:transfer",
    ),
    SensorEntityDescription(
        key="xonbatt",
        name="Transfer to Battery",
        icon="mdi:transfer",
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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
