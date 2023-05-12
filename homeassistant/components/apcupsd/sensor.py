"""Support for APCUPSd sensors."""
from __future__ import annotations

import logging

from apcaccess.status import ALL_UNITS

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, APCUPSdData

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorEntityDescription] = {
    "alarmdel": SensorEntityDescription(
        key="alarmdel",
        name="UPS Alarm Delay",
        icon="mdi:alarm",
    ),
    "ambtemp": SensorEntityDescription(
        key="ambtemp",
        name="UPS Ambient Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "apc": SensorEntityDescription(
        key="apc",
        name="UPS Status Data",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "apcmodel": SensorEntityDescription(
        key="apcmodel",
        name="UPS Model",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "badbatts": SensorEntityDescription(
        key="badbatts",
        name="UPS Bad Batteries",
        icon="mdi:information-outline",
    ),
    "battdate": SensorEntityDescription(
        key="battdate",
        name="UPS Battery Replaced",
        icon="mdi:calendar-clock",
    ),
    "battstat": SensorEntityDescription(
        key="battstat",
        name="UPS Battery Status",
        icon="mdi:information-outline",
    ),
    "battv": SensorEntityDescription(
        key="battv",
        name="UPS Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "bcharge": SensorEntityDescription(
        key="bcharge",
        name="UPS Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "cable": SensorEntityDescription(
        key="cable",
        name="UPS Cable Type",
        icon="mdi:ethernet-cable",
        entity_registry_enabled_default=False,
    ),
    "cumonbatt": SensorEntityDescription(
        key="cumonbatt",
        name="UPS Total Time on Battery",
        icon="mdi:timer-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "date": SensorEntityDescription(
        key="date",
        name="UPS Status Date",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    "dipsw": SensorEntityDescription(
        key="dipsw",
        name="UPS Dip Switch Settings",
        icon="mdi:information-outline",
    ),
    "dlowbatt": SensorEntityDescription(
        key="dlowbatt",
        name="UPS Low Battery Signal",
        icon="mdi:clock-alert",
    ),
    "driver": SensorEntityDescription(
        key="driver",
        name="UPS Driver",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "dshutd": SensorEntityDescription(
        key="dshutd",
        name="UPS Shutdown Delay",
        icon="mdi:timer-outline",
    ),
    "dwake": SensorEntityDescription(
        key="dwake",
        name="UPS Wake Delay",
        icon="mdi:timer-outline",
    ),
    "end apc": SensorEntityDescription(
        key="end apc",
        name="UPS Date and Time",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    "extbatts": SensorEntityDescription(
        key="extbatts",
        name="UPS External Batteries",
        icon="mdi:information-outline",
    ),
    "firmware": SensorEntityDescription(
        key="firmware",
        name="UPS Firmware Version",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "hitrans": SensorEntityDescription(
        key="hitrans",
        name="UPS Transfer High",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "hostname": SensorEntityDescription(
        key="hostname",
        name="UPS Hostname",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="UPS Ambient Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        icon="mdi:water-percent",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "itemp": SensorEntityDescription(
        key="itemp",
        name="UPS Internal Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "laststest": SensorEntityDescription(
        key="laststest",
        name="UPS Last Self Test",
        icon="mdi:calendar-clock",
    ),
    "lastxfer": SensorEntityDescription(
        key="lastxfer",
        name="UPS Last Transfer",
        icon="mdi:transfer",
        entity_registry_enabled_default=False,
    ),
    "linefail": SensorEntityDescription(
        key="linefail",
        name="UPS Input Voltage Status",
        icon="mdi:information-outline",
    ),
    "linefreq": SensorEntityDescription(
        key="linefreq",
        name="UPS Line Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "linev": SensorEntityDescription(
        key="linev",
        name="UPS Input Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "loadpct": SensorEntityDescription(
        key="loadpct",
        name="UPS Load",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "loadapnt": SensorEntityDescription(
        key="loadapnt",
        name="UPS Load Apparent Power",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
    "lotrans": SensorEntityDescription(
        key="lotrans",
        name="UPS Transfer Low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "mandate": SensorEntityDescription(
        key="mandate",
        name="UPS Manufacture Date",
        icon="mdi:calendar",
        entity_registry_enabled_default=False,
    ),
    "masterupd": SensorEntityDescription(
        key="masterupd",
        name="UPS Master Update",
        icon="mdi:information-outline",
    ),
    "maxlinev": SensorEntityDescription(
        key="maxlinev",
        name="UPS Input Voltage High",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "maxtime": SensorEntityDescription(
        key="maxtime",
        name="UPS Battery Timeout",
        icon="mdi:timer-off-outline",
    ),
    "mbattchg": SensorEntityDescription(
        key="mbattchg",
        name="UPS Battery Shutdown",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
    ),
    "minlinev": SensorEntityDescription(
        key="minlinev",
        name="UPS Input Voltage Low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "mintimel": SensorEntityDescription(
        key="mintimel",
        name="UPS Shutdown Time",
        icon="mdi:timer-outline",
    ),
    "model": SensorEntityDescription(
        key="model",
        name="UPS Model",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "nombattv": SensorEntityDescription(
        key="nombattv",
        name="UPS Battery Nominal Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "nominv": SensorEntityDescription(
        key="nominv",
        name="UPS Nominal Input Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "nomoutv": SensorEntityDescription(
        key="nomoutv",
        name="UPS Nominal Output Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "nompower": SensorEntityDescription(
        key="nompower",
        name="UPS Nominal Output Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    "nomapnt": SensorEntityDescription(
        key="nomapnt",
        name="UPS Nominal Apparent Power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
    ),
    "numxfers": SensorEntityDescription(
        key="numxfers",
        name="UPS Transfer Count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "outcurnt": SensorEntityDescription(
        key="outcurnt",
        name="UPS Output Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outputv": SensorEntityDescription(
        key="outputv",
        name="UPS Output Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "reg1": SensorEntityDescription(
        key="reg1",
        name="UPS Register 1 Fault",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "reg2": SensorEntityDescription(
        key="reg2",
        name="UPS Register 2 Fault",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "reg3": SensorEntityDescription(
        key="reg3",
        name="UPS Register 3 Fault",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "retpct": SensorEntityDescription(
        key="retpct",
        name="UPS Restore Requirement",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
    ),
    "selftest": SensorEntityDescription(
        key="selftest",
        name="UPS Self Test result",
        icon="mdi:information-outline",
    ),
    "sense": SensorEntityDescription(
        key="sense",
        name="UPS Sensitivity",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "serialno": SensorEntityDescription(
        key="serialno",
        name="UPS Serial Number",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "starttime": SensorEntityDescription(
        key="starttime",
        name="UPS Startup Time",
        icon="mdi:calendar-clock",
    ),
    "statflag": SensorEntityDescription(
        key="statflag",
        name="UPS Status Flag",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "status": SensorEntityDescription(
        key="status",
        name="UPS Status",
        icon="mdi:information-outline",
    ),
    "stesti": SensorEntityDescription(
        key="stesti",
        name="UPS Self Test Interval",
        icon="mdi:information-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "timeleft": SensorEntityDescription(
        key="timeleft",
        name="UPS Time Left",
        icon="mdi:clock-alert",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "tonbatt": SensorEntityDescription(
        key="tonbatt",
        name="UPS Time on Battery",
        icon="mdi:timer-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "upsmode": SensorEntityDescription(
        key="upsmode",
        name="UPS Mode",
        icon="mdi:information-outline",
    ),
    "upsname": SensorEntityDescription(
        key="upsname",
        name="UPS Name",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "version": SensorEntityDescription(
        key="version",
        name="UPS Daemon Info",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "xoffbat": SensorEntityDescription(
        key="xoffbat",
        name="UPS Transfer from Battery",
        icon="mdi:transfer",
    ),
    "xoffbatt": SensorEntityDescription(
        key="xoffbatt",
        name="UPS Transfer from Battery",
        icon="mdi:transfer",
    ),
    "xonbatt": SensorEntityDescription(
        key="xonbatt",
        name="UPS Transfer to Battery",
        icon="mdi:transfer",
    ),
}

SPECIFIC_UNITS = {"ITEMP": UnitOfTemperature.CELSIUS}
INFERRED_UNITS = {
    " Minutes": UnitOfTime.MINUTES,
    " Seconds": UnitOfTime.SECONDS,
    " Percent": PERCENTAGE,
    " Volts": UnitOfElectricPotential.VOLT,
    " Ampere": UnitOfElectricCurrent.AMPERE,
    " Volt-Ampere": UnitOfApparentPower.VOLT_AMPERE,
    " Watts": UnitOfPower.WATT,
    " Hz": UnitOfFrequency.HERTZ,
    " C": UnitOfTemperature.CELSIUS,
    " Percent Load Capacity": PERCENTAGE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the APCUPSd sensors from config entries."""
    data_service: APCUPSdData = hass.data[DOMAIN][config_entry.entry_id]

    # The resources from data service are in upper-case by default, but we use
    # lower cases throughout this integration.
    available_resources: set[str] = {k.lower() for k, _ in data_service.status.items()}

    entities = []
    for resource in available_resources:
        if resource not in SENSORS:
            _LOGGER.warning("Invalid resource from APCUPSd: %s", resource.upper())
            continue

        entities.append(APCUPSdSensor(data_service, SENSORS[resource]))

    async_add_entities(entities, update_before_add=True)


def infer_unit(value: str) -> tuple[str, str | None]:
    """If the value ends with any of the units from ALL_UNITS.

    Split the unit off the end of the value and return the value, unit tuple
    pair. Else return the original value and None as the unit.
    """

    for unit in ALL_UNITS:
        if value.endswith(unit):
            return value.removesuffix(unit), INFERRED_UNITS.get(unit, unit.strip())
    return value, None


class APCUPSdSensor(SensorEntity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(
        self,
        data_service: APCUPSdData,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        # Set up unique id and device info if serial number is available.
        if (serial_no := data_service.serial_no) is not None:
            self._attr_unique_id = f"{serial_no}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, serial_no)},
                model=data_service.model,
                manufacturer="APC",
                hw_version=data_service.hw_version,
                sw_version=data_service.sw_version,
            )

        self.entity_description = description
        self._data_service = data_service

    def update(self) -> None:
        """Get the latest status and use it to update our sensor state."""
        try:
            self._data_service.update()
        except OSError as ex:
            if self._attr_available:
                self._attr_available = False
                _LOGGER.exception("Got exception while fetching state: %s", ex)
            return

        self._attr_available = True
        key = self.entity_description.key.upper()
        if key not in self._data_service.status:
            self._attr_native_value = None
            return

        self._attr_native_value, inferred_unit = infer_unit(
            self._data_service.status[key]
        )
        if not self.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = inferred_unit
