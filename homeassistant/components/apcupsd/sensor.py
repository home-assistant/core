"""Support for APCUPSd sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final, override

import dateutil

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import LAST_S_TEST
from .coordinator import APCUPSdConfigEntry, APCUPSdCoordinator, APCUPSdData
from .entity import APCUPSdEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# List of useless sensors to ignore, since they are either provided in device
# information, or not useful at all
IGNORED_SENSORS: Final = {
    "apc",
    "end apc",
    "date",
    "apcmodel",
    "model",
    "firmware",
    "version",
    "upsname",
    "serialno",
}

# Sensors that only appear after an event since the last daemon restart: a self
# test for "laststest", a transfer to or from the battery for "xonbatt" and
# "xoffbatt". They are always added, and stay unknown until the event happens.
EVENT_SENSORS: Final = {LAST_S_TEST, "xoffbatt", "xonbatt"}


@dataclass(frozen=True, kw_only=True)
class APCUPSdSensorEntityDescription(SensorEntityDescription):
    """Describe an APCUPSd sensor with an optional value function."""

    value_fn: Callable[[APCUPSdData], StateType] | None = None
    required_resources: frozenset[str] = frozenset()


SENSORS: dict[str, APCUPSdSensorEntityDescription] = {
    "alarmdel": APCUPSdSensorEntityDescription(
        key="alarmdel",
        translation_key="alarm_delay",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ambtemp": APCUPSdSensorEntityDescription(
        key="ambtemp",
        translation_key="ambient_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "badbatts": APCUPSdSensorEntityDescription(
        key="badbatts",
        translation_key="bad_batteries",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battdate": APCUPSdSensorEntityDescription(
        key="battdate",
        translation_key="battery_replacement_date",
    ),
    "battstat": APCUPSdSensorEntityDescription(
        key="battstat",
        translation_key="battery_status",
    ),
    "battv": APCUPSdSensorEntityDescription(
        key="battv",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "bcharge": APCUPSdSensorEntityDescription(
        key="bcharge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "cable": APCUPSdSensorEntityDescription(
        key="cable",
        translation_key="cable_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "cumonbatt": APCUPSdSensorEntityDescription(
        key="cumonbatt",
        translation_key="total_time_on_battery",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
    ),
    "dipsw": APCUPSdSensorEntityDescription(
        key="dipsw",
        translation_key="dip_switch_settings",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "dlowbatt": APCUPSdSensorEntityDescription(
        key="dlowbatt",
        translation_key="low_battery_signal",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "driver": APCUPSdSensorEntityDescription(
        key="driver",
        translation_key="driver",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "dshutd": APCUPSdSensorEntityDescription(
        key="dshutd",
        translation_key="shutdown_delay",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "dwake": APCUPSdSensorEntityDescription(
        key="dwake",
        translation_key="wake_delay",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "extbatts": APCUPSdSensorEntityDescription(
        key="extbatts",
        translation_key="external_batteries",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "hitrans": APCUPSdSensorEntityDescription(
        key="hitrans",
        translation_key="transfer_high",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "hostname": APCUPSdSensorEntityDescription(
        key="hostname",
        translation_key="hostname",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "humidity": APCUPSdSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "itemp": APCUPSdSensorEntityDescription(
        key="itemp",
        translation_key="internal_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    LAST_S_TEST: APCUPSdSensorEntityDescription(
        key=LAST_S_TEST,
        translation_key="last_self_test",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    "lastxfer": APCUPSdSensorEntityDescription(
        key="lastxfer",
        translation_key="last_transfer",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "linefail": APCUPSdSensorEntityDescription(
        key="linefail",
        translation_key="line_failure",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "linefreq": APCUPSdSensorEntityDescription(
        key="linefreq",
        translation_key="line_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "linev": APCUPSdSensorEntityDescription(
        key="linev",
        translation_key="line_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "loadpct": APCUPSdSensorEntityDescription(
        key="loadpct",
        translation_key="load_capacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "loadapnt": APCUPSdSensorEntityDescription(
        key="loadapnt",
        translation_key="apparent_power",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "lotrans": APCUPSdSensorEntityDescription(
        key="lotrans",
        translation_key="transfer_low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "mandate": APCUPSdSensorEntityDescription(
        key="mandate",
        translation_key="manufacture_date",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "masterupd": APCUPSdSensorEntityDescription(
        key="masterupd",
        translation_key="master_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "maxlinev": APCUPSdSensorEntityDescription(
        key="maxlinev",
        translation_key="input_voltage_high",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "maxtime": APCUPSdSensorEntityDescription(
        key="maxtime",
        translation_key="max_time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "mbattchg": APCUPSdSensorEntityDescription(
        key="mbattchg",
        translation_key="max_battery_charge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "minlinev": APCUPSdSensorEntityDescription(
        key="minlinev",
        translation_key="input_voltage_low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "mintimel": APCUPSdSensorEntityDescription(
        key="mintimel",
        translation_key="min_time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "nombattv": APCUPSdSensorEntityDescription(
        key="nombattv",
        translation_key="battery_nominal_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "nominv": APCUPSdSensorEntityDescription(
        key="nominv",
        translation_key="nominal_input_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "nomoutv": APCUPSdSensorEntityDescription(
        key="nomoutv",
        translation_key="nominal_output_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "nompower": APCUPSdSensorEntityDescription(
        key="nompower",
        translation_key="nominal_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "nomapnt": APCUPSdSensorEntityDescription(
        key="nomapnt",
        translation_key="nominal_apparent_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "numxfers": APCUPSdSensorEntityDescription(
        key="numxfers",
        translation_key="transfer_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "outcurnt": APCUPSdSensorEntityDescription(
        key="outcurnt",
        translation_key="output_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outputv": APCUPSdSensorEntityDescription(
        key="outputv",
        translation_key="output_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "reg1": APCUPSdSensorEntityDescription(
        key="reg1",
        translation_key="register_1_fault",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "reg2": APCUPSdSensorEntityDescription(
        key="reg2",
        translation_key="register_2_fault",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "reg3": APCUPSdSensorEntityDescription(
        key="reg3",
        translation_key="register_3_fault",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "retpct": APCUPSdSensorEntityDescription(
        key="retpct",
        translation_key="restore_capacity",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "selftest": APCUPSdSensorEntityDescription(
        key="selftest",
        translation_key="self_test_result",
    ),
    "sense": APCUPSdSensorEntityDescription(
        key="sense",
        translation_key="sensitivity",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "starttime": APCUPSdSensorEntityDescription(
        key="starttime",
        translation_key="startup_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "statflag": APCUPSdSensorEntityDescription(
        key="statflag",
        translation_key="online_status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "status": APCUPSdSensorEntityDescription(
        key="status",
        translation_key="status",
    ),
    "stesti": APCUPSdSensorEntityDescription(
        key="stesti",
        translation_key="self_test_interval",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "timeleft": APCUPSdSensorEntityDescription(
        key="timeleft",
        translation_key="time_left",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
    ),
    "tonbatt": APCUPSdSensorEntityDescription(
        key="tonbatt",
        translation_key="time_on_battery",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
    ),
    "upsmode": APCUPSdSensorEntityDescription(
        key="upsmode",
        translation_key="ups_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "xoffbat": APCUPSdSensorEntityDescription(
        key="xoffbat",
        translation_key="transfer_from_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "xoffbatt": APCUPSdSensorEntityDescription(
        key="xoffbatt",
        translation_key="transfer_from_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "xonbatt": APCUPSdSensorEntityDescription(
        key="xonbatt",
        translation_key="transfer_to_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

DERIVED_SENSORS: Final[tuple[APCUPSdSensorEntityDescription, ...]] = (
    APCUPSdSensorEntityDescription(
        key="output_power",
        translation_key="output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        required_resources=frozenset({"loadpct", "nompower"}),
        value_fn=lambda data: (
            float(infer_unit(data["LOADPCT"])[0])
            * float(infer_unit(data["NOMPOWER"])[0])
            / 100
        ),
    ),
)

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
    config_entry: APCUPSdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the APCUPSd sensors from config entries."""
    coordinator = config_entry.runtime_data

    # The resource keys in the data dict collected in the coordinator is in upper-case
    # by default, but we use lower cases throughout this integration.
    available_resources: set[str] = {k.lower() for k, _ in coordinator.data.items()}

    entities = []

    # We sort the resources to ensure the order of entities created is
    # deterministic
    for resource in sorted(available_resources | EVENT_SENSORS):
        if resource in IGNORED_SENSORS:
            continue
        if resource not in SENSORS:
            _LOGGER.warning("Invalid resource from APCUPSd: %s", resource.upper())
            continue

        entities.append(APCUPSdSensor(coordinator, SENSORS[resource]))

    entities.extend(
        APCUPSdSensor(coordinator, description)
        for description in DERIVED_SENSORS
        if description.required_resources <= available_resources
    )

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


class APCUPSdSensor(APCUPSdEntity, SensorEntity):
    """Representation of a sensor entity for APCUPSd status values."""

    entity_description: APCUPSdSensorEntityDescription

    def __init__(
        self,
        coordinator: APCUPSdCoordinator,
        description: APCUPSdSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)

        # Initial update of attributes.
        self._update_attrs()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        if self.entity_description.value_fn is not None:
            try:
                self._attr_native_value = self.entity_description.value_fn(
                    self.coordinator.data
                )
            except KeyError, ValueError:
                self._attr_native_value = None
            return

        key = self.entity_description.key.upper()
        # For most sensors the key will always be available for
        # each refresh. However, some sensors (e.g., "laststest")
        # will only appear after certain event occurs (e.g., a
        # self test is performed) and may disappear again after
        # certain event. So we mark the state as "unknown"
        # when it becomes unknown after such events.
        if key not in self.coordinator.data:
            self._attr_native_value = None
            return

        data = self.coordinator.data[key]

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            # The date could be "N/A" for certain fields
            # (e.g., XOFFBATT), indicating there is no value yet.
            if data == "N/A":
                self._attr_native_value = None
                return

            try:
                self._attr_native_value = dateutil.parser.parse(data)
            except dateutil.parser.ParserError, OverflowError:
                # If parsing fails we should mark it as unknown,
                # with a log for further debugging.
                _LOGGER.warning('Failed to parse date for %s: "%s"', key, data)
                self._attr_native_value = None
            return

        self._attr_native_value, inferred_unit = infer_unit(data)
        if not self.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = inferred_unit
