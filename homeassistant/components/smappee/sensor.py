"""Support for monitoring a Smappee energy sensor."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


@dataclass
class SmappeeRequiredKeysMixin:
    """Mixin for required keys."""

    sensor_id: str


@dataclass
class SmappeeSensorEntityDescription(SensorEntityDescription, SmappeeRequiredKeysMixin):
    """Describes Smappee sensor entity."""


@dataclass
class SmappeePollingSensorEntityDescription(SmappeeSensorEntityDescription):
    """Describes Smappee sensor entity."""

    local_polling: bool = False


@dataclass
class SmappeeVoltageSensorEntityDescription(SmappeeSensorEntityDescription):
    """Describes Smappee sensor entity."""

    phase_types: set[str] = field(default_factory=set)


TREND_SENSORS: tuple[SmappeePollingSensorEntityDescription, ...] = (
    SmappeePollingSensorEntityDescription(
        key="total_power",
        name="Total consumption - Active power",
        native_unit_of_measurement=POWER_WATT,
        sensor_id="total_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        local_polling=True,  # both cloud and local
    ),
    SmappeePollingSensorEntityDescription(
        key="alwayson",
        name="Always on - Active power",
        native_unit_of_measurement=POWER_WATT,
        sensor_id="alwayson",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SmappeePollingSensorEntityDescription(
        key="power_today",
        name="Total consumption - Today",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        sensor_id="power_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmappeePollingSensorEntityDescription(
        key="power_current_hour",
        name="Total consumption - Current hour",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        sensor_id="power_current_hour",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmappeePollingSensorEntityDescription(
        key="power_last_5_minutes",
        name="Total consumption - Last 5 minutes",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        sensor_id="power_last_5_minutes",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmappeePollingSensorEntityDescription(
        key="alwayson_today",
        name="Always on - Today",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        sensor_id="alwayson_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
REACTIVE_SENSORS: tuple[SmappeeSensorEntityDescription, ...] = (
    SmappeeSensorEntityDescription(
        key="total_reactive_power",
        name="Total consumption - Reactive power",
        native_unit_of_measurement=POWER_WATT,
        sensor_id="total_reactive_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
SOLAR_SENSORS: tuple[SmappeePollingSensorEntityDescription, ...] = (
    SmappeePollingSensorEntityDescription(
        key="solar_power",
        name="Total production - Active power",
        native_unit_of_measurement=POWER_WATT,
        sensor_id="solar_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        local_polling=True,  # both cloud and local
    ),
    SmappeePollingSensorEntityDescription(
        key="solar_today",
        name="Total production - Today",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        sensor_id="solar_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmappeePollingSensorEntityDescription(
        key="solar_current_hour",
        name="Total production - Current hour",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        sensor_id="solar_current_hour",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
VOLTAGE_SENSORS: tuple[SmappeeVoltageSensorEntityDescription, ...] = (
    SmappeeVoltageSensorEntityDescription(
        key="phase_voltages_a",
        name="Phase voltages - A",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        sensor_id="phase_voltage_a",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        phase_types={"ONE", "TWO", "THREE_STAR", "THREE_DELTA"},
    ),
    SmappeeVoltageSensorEntityDescription(
        key="phase_voltages_b",
        name="Phase voltages - B",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        sensor_id="phase_voltage_b",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        phase_types={"TWO", "THREE_STAR", "THREE_DELTA"},
    ),
    SmappeeVoltageSensorEntityDescription(
        key="phase_voltages_c",
        name="Phase voltages - C",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        sensor_id="phase_voltage_c",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        phase_types={"THREE_STAR"},
    ),
    SmappeeVoltageSensorEntityDescription(
        key="line_voltages_a",
        name="Line voltages - A",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        sensor_id="line_voltage_a",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        phase_types={"ONE", "TWO", "THREE_STAR", "THREE_DELTA"},
    ),
    SmappeeVoltageSensorEntityDescription(
        key="line_voltages_b",
        name="Line voltages - B",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        sensor_id="line_voltage_b",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        phase_types={"TWO", "THREE_STAR", "THREE_DELTA"},
    ),
    SmappeeVoltageSensorEntityDescription(
        key="line_voltages_c",
        name="Line voltages - C",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        sensor_id="line_voltage_c",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        phase_types={"THREE_STAR", "THREE_DELTA"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smappee sensor."""
    smappee_base = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for service_location in smappee_base.smappee.service_locations.values():
        # Add all basic sensors (realtime values and aggregators)
        # Some are available in local only env
        entities.extend(
            [
                SmappeeSensor(
                    smappee_base=smappee_base,
                    service_location=service_location,
                    description=description,
                )
                for description in TREND_SENSORS
                if not service_location.local_polling or description.local_polling
            ]
        )

        if service_location.has_reactive_value:
            entities.extend(
                [
                    SmappeeSensor(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        description=description,
                    )
                    for description in REACTIVE_SENSORS
                ]
            )

        # Add solar sensors (some are available in local only env)
        if service_location.has_solar_production:
            entities.extend(
                [
                    SmappeeSensor(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        description=description,
                    )
                    for description in SOLAR_SENSORS
                    if not service_location.local_polling or description.local_polling
                ]
            )

        # Add all CT measurements
        entities.extend(
            [
                SmappeeSensor(
                    smappee_base=smappee_base,
                    service_location=service_location,
                    description=SmappeeSensorEntityDescription(
                        key="load",
                        name=measurement.name,
                        native_unit_of_measurement=POWER_WATT,
                        sensor_id=measurement_id,
                        device_class=SensorDeviceClass.POWER,
                        state_class=SensorStateClass.MEASUREMENT,
                    ),
                )
                for measurement_id, measurement in service_location.measurements.items()
            ]
        )

        # Add phase- and line voltages if available
        if service_location.has_voltage_values:
            entities.extend(
                [
                    SmappeeSensor(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        description=description,
                    )
                    for description in VOLTAGE_SENSORS
                    if (
                        service_location.phase_type in description.phase_types
                        and not (
                            description.key.startswith("line_")
                            and service_location.local_polling
                        )
                    )
                ]
            )

        # Add Gas and Water sensors
        entities.extend(
            [
                SmappeeSensor(
                    smappee_base=smappee_base,
                    service_location=service_location,
                    description=SmappeeSensorEntityDescription(
                        key="sensor",
                        name=channel.get("name"),
                        icon=(
                            "mdi:water"
                            if channel.get("type") == "water"
                            else "mdi:gas-cylinder"
                        ),
                        native_unit_of_measurement=channel.get("uom"),
                        sensor_id=f"{sensor_id}-{channel.get('channel')}",
                        state_class=SensorStateClass.MEASUREMENT,
                    ),
                )
                for sensor_id, sensor in service_location.sensors.items()
                for channel in sensor.channels
            ]
        )

        # Add today_energy_kwh sensors for switches
        entities.extend(
            [
                SmappeeSensor(
                    smappee_base=smappee_base,
                    service_location=service_location,
                    description=SmappeeSensorEntityDescription(
                        key="switch",
                        name=f"{actuator.name} - energy today",
                        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                        sensor_id=actuator_id,
                        device_class=SensorDeviceClass.ENERGY,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                    ),
                )
                for actuator_id, actuator in service_location.actuators.items()
                if actuator.type == "SWITCH" and not service_location.local_polling
            ]
        )

    async_add_entities(entities, True)


class SmappeeSensor(SensorEntity):
    """Implementation of a Smappee sensor."""

    entity_description: SmappeeSensorEntityDescription

    def __init__(
        self,
        smappee_base,
        service_location,
        description: SmappeeSensorEntityDescription,
    ):
        """Initialize the Smappee sensor."""
        self.entity_description = description
        self._smappee_base = smappee_base
        self._service_location = service_location

    @property
    def name(self):
        """Return the name for this sensor."""
        sensor_key = self.entity_description.key
        sensor_name = self.entity_description.name
        if sensor_key in ("sensor", "load", "switch"):
            return (
                f"{self._service_location.service_location_name} - "
                f"{sensor_key.title()} - {sensor_name}"
            )

        return f"{self._service_location.service_location_name} - {sensor_name}"

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        sensor_key = self.entity_description.key
        if sensor_key in ("load", "sensor", "switch"):
            return (
                f"{self._service_location.device_serial_number}-"
                f"{self._service_location.service_location_id}-"
                f"{sensor_key}-{self.entity_description.sensor_id}"
            )

        return (
            f"{self._service_location.device_serial_number}-"
            f"{self._service_location.service_location_id}-"
            f"{sensor_key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for this sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._service_location.device_serial_number)},
            manufacturer="Smappee",
            model=self._service_location.device_model,
            name=self._service_location.service_location_name,
            sw_version=self._service_location.firmware_version,
        )

    async def async_update(self):
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        sensor_key = self.entity_description.key
        if sensor_key == "total_power":
            self._attr_native_value = self._service_location.total_power
        elif sensor_key == "total_reactive_power":
            self._attr_native_value = self._service_location.total_reactive_power
        elif sensor_key == "solar_power":
            self._attr_native_value = self._service_location.solar_power
        elif sensor_key == "alwayson":
            self._attr_native_value = self._service_location.alwayson
        elif sensor_key in (
            "phase_voltages_a",
            "phase_voltages_b",
            "phase_voltages_c",
        ):
            phase_voltages = self._service_location.phase_voltages
            if phase_voltages is not None:
                if sensor_key == "phase_voltages_a":
                    self._attr_native_value = phase_voltages[0]
                elif sensor_key == "phase_voltages_b":
                    self._attr_native_value = phase_voltages[1]
                elif sensor_key == "phase_voltages_c":
                    self._attr_native_value = phase_voltages[2]
        elif sensor_key in ("line_voltages_a", "line_voltages_b", "line_voltages_c"):
            line_voltages = self._service_location.line_voltages
            if line_voltages is not None:
                if sensor_key == "line_voltages_a":
                    self._attr_native_value = line_voltages[0]
                elif sensor_key == "line_voltages_b":
                    self._attr_native_value = line_voltages[1]
                elif sensor_key == "line_voltages_c":
                    self._attr_native_value = line_voltages[2]
        elif sensor_key in (
            "power_today",
            "power_current_hour",
            "power_last_5_minutes",
            "solar_today",
            "solar_current_hour",
            "alwayson_today",
        ):
            trend_value = self._service_location.aggregated_values.get(sensor_key)
            self._attr_native_value = (
                round(trend_value) if trend_value is not None else None
            )
        elif sensor_key == "load":
            self._attr_native_value = self._service_location.measurements.get(
                self.entity_description.sensor_id
            ).active_total
        elif sensor_key == "sensor":
            sensor_id, channel_id = self.entity_description.sensor_id.split("-")
            sensor = self._service_location.sensors.get(int(sensor_id))
            for channel in sensor.channels:
                if channel.get("channel") == int(channel_id):
                    self._attr_native_value = channel.get("value_today")
        elif sensor_key == "switch":
            cons = self._service_location.actuators.get(
                self.entity_description.sensor_id
            ).consumption_today
            if cons is not None:
                self._attr_native_value = round(cons / 1000.0, 2)
