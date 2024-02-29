"""Support for APCUPSd sensors."""
from __future__ import annotations

import logging

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, APCUPSdCoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorEntityDescription] = {
    "alarmdel": SensorEntityDescription(
        key="alarmdel",
        translation_key="alarm_delay",
        name="UPS Alarm Delay",
    ),
    "ambtemp": SensorEntityDescription(
        key="ambtemp",
        name="UPS Ambient Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "apc": SensorEntityDescription(
        key="apc",
        translation_key="apc_status",
        name="UPS Status Data",
        entity_registry_enabled_default=False,
    ),
    "apcmodel": SensorEntityDescription(
        key="apcmodel",
        translation_key="apc_model",
        name="UPS Model",
        entity_registry_enabled_default=False,
    ),
    "badbatts": SensorEntityDescription(
        key="badbatts",
        translation_key="bad_batteries",
        name="UPS Bad Batteries",
    ),
    "battdate": SensorEntityDescription(
        key="battdate",
        translation_key="battery_replacement_date",
        name="UPS Battery Replaced",
    ),
    "battstat": SensorEntityDescription(
        key="battstat",
        translation_key="battery_status",
        name="UPS Battery Status",
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
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "cable": SensorEntityDescription(
        key="cable",
        translation_key="cable_type",
        name="UPS Cable Type",
        entity_registry_enabled_default=False,
    ),
    "cumonbatt": SensorEntityDescription(
        key="cumonbatt",
        translation_key="total_time_on_battery",
        name="UPS Total Time on Battery",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "date": SensorEntityDescription(
        key="date",
        translation_key="date",
        name="UPS Status Date",
        entity_registry_enabled_default=False,
    ),
    "dipsw": SensorEntityDescription(
        key="dipsw",
        translation_key="dip_switch_settings",
        name="UPS Dip Switch Settings",
    ),
    "dlowbatt": SensorEntityDescription(
        key="dlowbatt",
        translation_key="low_battery_signal",
        name="UPS Low Battery Signal",
    ),
    "driver": SensorEntityDescription(
        key="driver",
        translation_key="driver",
        name="UPS Driver",
        entity_registry_enabled_default=False,
    ),
    "dshutd": SensorEntityDescription(
        key="dshutd",
        translation_key="shutdown_delay",
        name="UPS Shutdown Delay",
    ),
    "dwake": SensorEntityDescription(
        key="dwake",
        translation_key="wake_delay",
        name="UPS Wake Delay",
    ),
    "end apc": SensorEntityDescription(
        key="end apc",
        translation_key="date_and_time",
        name="UPS Date and Time",
        entity_registry_enabled_default=False,
    ),
    "extbatts": SensorEntityDescription(
        key="extbatts",
        translation_key="external_batteries",
        name="UPS External Batteries",
    ),
    "firmware": SensorEntityDescription(
        key="firmware",
        translation_key="firmware_version",
        name="UPS Firmware Version",
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
        translation_key="hostname",
        name="UPS Hostname",
        entity_registry_enabled_default=False,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="UPS Ambient Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
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
        translation_key="last_self_test",
        name="UPS Last Self Test",
    ),
    "lastxfer": SensorEntityDescription(
        key="lastxfer",
        translation_key="last_transfer",
        name="UPS Last Transfer",
        entity_registry_enabled_default=False,
    ),
    "linefail": SensorEntityDescription(
        key="linefail",
        translation_key="line_failure",
        name="UPS Input Voltage Status",
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
        translation_key="load_capacity",
        name="UPS Load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "loadapnt": SensorEntityDescription(
        key="loadapnt",
        translation_key="apparent_power",
        name="UPS Load Apparent Power",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "lotrans": SensorEntityDescription(
        key="lotrans",
        name="UPS Transfer Low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "mandate": SensorEntityDescription(
        key="mandate",
        translation_key="manufacture_date",
        name="UPS Manufacture Date",
        entity_registry_enabled_default=False,
    ),
    "masterupd": SensorEntityDescription(
        key="masterupd",
        translation_key="master_update",
        name="UPS Master Update",
    ),
    "maxlinev": SensorEntityDescription(
        key="maxlinev",
        name="UPS Input Voltage High",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "maxtime": SensorEntityDescription(
        key="maxtime",
        translation_key="max_time",
        name="UPS Battery Timeout",
    ),
    "mbattchg": SensorEntityDescription(
        key="mbattchg",
        translation_key="max_battery_charge",
        name="UPS Battery Shutdown",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "minlinev": SensorEntityDescription(
        key="minlinev",
        name="UPS Input Voltage Low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "mintimel": SensorEntityDescription(
        key="mintimel",
        translation_key="min_time",
        name="UPS Shutdown Time",
    ),
    "model": SensorEntityDescription(
        key="model",
        translation_key="model",
        name="UPS Model",
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
        translation_key="transfer_count",
        name="UPS Transfer Count",
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
        translation_key="register_1_fault",
        name="UPS Register 1 Fault",
        entity_registry_enabled_default=False,
    ),
    "reg2": SensorEntityDescription(
        key="reg2",
        translation_key="register_2_fault",
        name="UPS Register 2 Fault",
        entity_registry_enabled_default=False,
    ),
    "reg3": SensorEntityDescription(
        key="reg3",
        translation_key="register_3_fault",
        name="UPS Register 3 Fault",
        entity_registry_enabled_default=False,
    ),
    "retpct": SensorEntityDescription(
        key="retpct",
        translation_key="restore_capacity",
        name="UPS Restore Requirement",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "selftest": SensorEntityDescription(
        key="selftest",
        translation_key="self_test_result",
        name="UPS Self Test result",
    ),
    "sense": SensorEntityDescription(
        key="sense",
        translation_key="sensitivity",
        name="UPS Sensitivity",
        entity_registry_enabled_default=False,
    ),
    "serialno": SensorEntityDescription(
        key="serialno",
        translation_key="serial_number",
        name="UPS Serial Number",
        entity_registry_enabled_default=False,
    ),
    "starttime": SensorEntityDescription(
        key="starttime",
        translation_key="startup_time",
        name="UPS Startup Time",
    ),
    "statflag": SensorEntityDescription(
        key="statflag",
        translation_key="online_status",
        name="UPS Status Flag",
        entity_registry_enabled_default=False,
    ),
    "status": SensorEntityDescription(
        key="status",
        translation_key="status",
        name="UPS Status",
    ),
    "stesti": SensorEntityDescription(
        key="stesti",
        translation_key="self_test_interval",
        name="UPS Self Test Interval",
    ),
    "timeleft": SensorEntityDescription(
        key="timeleft",
        translation_key="time_left",
        name="UPS Time Left",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "tonbatt": SensorEntityDescription(
        key="tonbatt",
        translation_key="time_on_battery",
        name="UPS Time on Battery",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "upsmode": SensorEntityDescription(
        key="upsmode",
        translation_key="ups_mode",
        name="UPS Mode",
    ),
    "upsname": SensorEntityDescription(
        key="upsname",
        translation_key="ups_name",
        name="UPS Name",
        entity_registry_enabled_default=False,
    ),
    "version": SensorEntityDescription(
        key="version",
        translation_key="version",
        name="UPS Daemon Info",
        entity_registry_enabled_default=False,
    ),
    "xoffbat": SensorEntityDescription(
        key="xoffbat",
        translation_key="transfer_from_battery",
        name="UPS Transfer from Battery",
    ),
    "xoffbatt": SensorEntityDescription(
        key="xoffbatt",
        translation_key="transfer_from_battery",
        name="UPS Transfer from Battery",
    ),
    "xonbatt": SensorEntityDescription(
        key="xonbatt",
        translation_key="transfer_to_battery",
        name="UPS Transfer to Battery",
    ),
}

INFERRED_UNITS = {
    " Minutes": UnitOfTime.MINUTES,
    " Seconds": UnitOfTime.SECONDS,
    " Percent": PERCENTAGE,
    " Volts": UnitOfElectricPotential.VOLT,
    " Ampere": UnitOfElectricCurrent.AMPERE,
    " Amps": UnitOfElectricCurrent.AMPERE,
    " Volt-Ampere": UnitOfApparentPower.VOLT_AMPERE,
    " VA": UnitOfApparentPower.VOLT_AMPERE,
    " Watts": UnitOfPower.WATT,
    " Hz": UnitOfFrequency.HERTZ,
    " C": UnitOfTemperature.CELSIUS,
    # APCUPSd reports data for "itemp" field (eventually represented by UPS Internal
    # Temperature sensor in this integration) with a trailing "Internal", e.g.,
    # "34.6 C Internal". Here we create a fake unit " C Internal" to handle this case.
    " C Internal": UnitOfTemperature.CELSIUS,
    " Percent Load Capacity": PERCENTAGE,
    # "stesti" field (Self Test Interval) field could report a "days" unit, e.g.,
    # "7 days", so here we add support for it.
    " days": UnitOfTime.DAYS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the APCUPSd sensors from config entries."""
    coordinator: APCUPSdCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # The resource keys in the data dict collected in the coordinator is in upper-case
    # by default, but we use lower cases throughout this integration.
    available_resources: set[str] = {k.lower() for k, _ in coordinator.data.items()}

    entities = []
    for resource in available_resources:
        if resource not in SENSORS:
            _LOGGER.warning("Invalid resource from APCUPSd: %s", resource.upper())
            continue

        entities.append(APCUPSdSensor(coordinator, SENSORS[resource]))

    async_add_entities(entities)


def infer_unit(value: str) -> tuple[str, str | None]:
    """If the value ends with any of the units from supported units.

    Split the unit off the end of the value and return the value, unit tuple
    pair. Else return the original value and None as the unit.
    """

    for unit, ha_unit in INFERRED_UNITS.items():
        if value.endswith(unit):
            return value.removesuffix(unit), ha_unit

    return value, None


class APCUPSdSensor(CoordinatorEntity[APCUPSdCoordinator], SensorEntity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(
        self,
        coordinator: APCUPSdCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, context=description.key.upper())

        # Set up unique id and device info if serial number is available.
        if (serial_no := coordinator.ups_serial_no) is not None:
            self._attr_unique_id = f"{serial_no}_{description.key}"

        self.entity_description = description
        self._attr_device_info = coordinator.device_info

        # Initial update of attributes.
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        key = self.entity_description.key.upper()
        self._attr_native_value, inferred_unit = infer_unit(self.coordinator.data[key])
        if not self.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = inferred_unit
