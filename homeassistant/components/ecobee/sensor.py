"""Support for Ecobee sensors."""

from dataclasses import dataclass

from pyecobee.const import ECOBEE_STATE_CALIBRATING, ECOBEE_STATE_UNKNOWN

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcobeeConfigEntry
from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER


@dataclass(frozen=True, kw_only=True)
class EcobeeSensorEntityDescription(SensorEntityDescription):
    """Represent the ecobee sensor entity description."""

    runtime_key: str | None


SENSOR_TYPES: tuple[EcobeeSensorEntityDescription, ...] = (
    EcobeeSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        runtime_key=None,
    ),
    EcobeeSensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        runtime_key=None,
    ),
    EcobeeSensorEntityDescription(
        key="co2PPM",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        runtime_key="actualCO2",
    ),
    EcobeeSensorEntityDescription(
        key="vocPPM",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        runtime_key="actualVOC",
    ),
    EcobeeSensorEntityDescription(
        key="airQuality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        runtime_key="actualAQScore",
    ),
)


def _remote_sensor_unique_id(
    thermostat: dict, sensor: dict, description: EcobeeSensorEntityDescription
) -> str:
    """Build the unique_id used by EcobeeSensor for a remote sensor capability."""
    if "code" in sensor:
        return f"{sensor['code']}-{description.device_class}"
    return f"{thermostat['identifier']}-{sensor['id']}-{description.device_class}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcobeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ecobee sensors."""
    data = config_entry.runtime_data
    entities: list[EcobeeSensor] = []
    seen_unique_ids: set[str] = set()
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                for description in SENSOR_TYPES:
                    if description.key != item["type"]:
                        continue
                    # Deduplicate at setup time: some thermostats return the
                    # same sensor twice in remoteSensors, and SmartSensors
                    # paired to multiple thermostats share a `code`. Without
                    # this dedup the later registration is silently dropped
                    # by entity_platform with an "already exists" ERROR log.
                    unique_id = _remote_sensor_unique_id(
                        thermostat, sensor, description
                    )
                    if unique_id in seen_unique_ids:
                        continue
                    seen_unique_ids.add(unique_id)
                    entities.append(
                        EcobeeSensor(data, sensor["name"], index, description)
                    )

    async_add_entities(entities, True)


class EcobeeSensor(SensorEntity):
    """Representation of an Ecobee sensor."""

    _attr_has_entity_name = True

    entity_description: EcobeeSensorEntityDescription

    def __init__(
        self,
        data,
        sensor_name,
        sensor_index,
        description: EcobeeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.data = data
        self.sensor_name = sensor_name
        self.index = sensor_index
        self._state = None

    @property
    def unique_id(self) -> str | None:
        """Return a unique identifier for this sensor."""
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                thermostat = self.data.ecobee.get_thermostat(self.index)
                return _remote_sensor_unique_id(
                    thermostat, sensor, self.entity_description
                )
        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""
        identifier = None
        model = None
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            if "code" in sensor:
                identifier = sensor["code"]
                model = "ecobee Room Sensor"
            else:
                thermostat = self.data.ecobee.get_thermostat(self.index)
                identifier = thermostat["identifier"]
                try:
                    model = (
                        f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
                    )
                except KeyError:
                    # Ecobee model is not in our list
                    model = None
            break

        if identifier is not None and model is not None:
            return DeviceInfo(
                identifiers={(DOMAIN, identifier)},
                manufacturer=MANUFACTURER,
                model=model,
                name=self.sensor_name,
            )
        return None

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        thermostat = self.data.ecobee.get_thermostat(self.index)
        return thermostat["runtime"]["connected"]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._state in (
            ECOBEE_STATE_CALIBRATING,
            ECOBEE_STATE_UNKNOWN,
            "unknown",
        ):
            return None

        if self.entity_description.key == "temperature":
            return float(self._state) / 10

        return self._state

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != self.entity_description.key:
                    continue
                if self.entity_description.runtime_key is None:
                    self._state = item["value"]
                else:
                    thermostat = self.data.ecobee.get_thermostat(self.index)
                    self._state = thermostat["runtime"][
                        self.entity_description.runtime_key
                    ]
                break
