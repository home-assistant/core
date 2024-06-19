"""Support for deCONZ sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from pydeconz.interfaces.sensors import SensorResources
from pydeconz.models.event import EventType
from pydeconz.models.sensor import SensorBase as PydeconzSensorBase
from pydeconz.models.sensor.air_quality import AirQuality
from pydeconz.models.sensor.carbon_dioxide import CarbonDioxide
from pydeconz.models.sensor.consumption import Consumption
from pydeconz.models.sensor.daylight import DAYLIGHT_STATUS, Daylight
from pydeconz.models.sensor.formaldehyde import Formaldehyde
from pydeconz.models.sensor.generic_status import GenericStatus
from pydeconz.models.sensor.humidity import Humidity
from pydeconz.models.sensor.light_level import LightLevel
from pydeconz.models.sensor.moisture import Moisture
from pydeconz.models.sensor.particulate_matter import ParticulateMatter
from pydeconz.models.sensor.power import Power
from pydeconz.models.sensor.pressure import Pressure
from pydeconz.models.sensor.switch import Switch
from pydeconz.models.sensor.temperature import Temperature
from pydeconz.models.sensor.time import Time

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import ATTR_DARK, ATTR_ON
from .deconz_device import DeconzDevice
from .hub import DeconzHub

PROVIDES_EXTRA_ATTRIBUTES = (
    "battery",
    "consumption",
    "daylight_status",
    "humidity",
    "light_level",
    "power",
    "pressure",
    "status",
    "temperature",
)

ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_DAYLIGHT = "daylight"
ATTR_EVENT_ID = "event_id"


T = TypeVar(
    "T",
    AirQuality,
    CarbonDioxide,
    Consumption,
    Daylight,
    Formaldehyde,
    GenericStatus,
    Humidity,
    LightLevel,
    Moisture,
    ParticulateMatter,
    Power,
    Pressure,
    Temperature,
    Time,
    PydeconzSensorBase,
)


@dataclass(frozen=True, kw_only=True)
class DeconzSensorDescription(Generic[T], SensorEntityDescription):
    """Class describing deCONZ binary sensor entities."""

    instance_check: type[T] | None = None
    name_suffix: str = ""
    old_unique_id_suffix: str = ""
    supported_fn: Callable[[T], bool]
    update_key: str
    value_fn: Callable[[T], datetime | StateType]


ENTITY_DESCRIPTIONS: tuple[DeconzSensorDescription, ...] = (
    DeconzSensorDescription[AirQuality](
        key="air_quality",
        supported_fn=lambda device: device.supports_air_quality,
        update_key="airquality",
        value_fn=lambda device: device.air_quality,
        instance_check=AirQuality,
    ),
    DeconzSensorDescription[AirQuality](
        key="air_quality_ppb",
        supported_fn=lambda device: device.air_quality_ppb is not None,
        update_key="airqualityppb",
        value_fn=lambda device: device.air_quality_ppb,
        instance_check=AirQuality,
        name_suffix="PPB",
        old_unique_id_suffix="ppb",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
    ),
    DeconzSensorDescription[AirQuality](
        key="air_quality_formaldehyde",
        supported_fn=lambda device: device.air_quality_formaldehyde is not None,
        update_key="airquality_formaldehyde_density",
        value_fn=lambda device: device.air_quality_formaldehyde,
        instance_check=AirQuality,
        name_suffix="CH2O",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    DeconzSensorDescription[AirQuality](
        key="air_quality_co2",
        supported_fn=lambda device: device.air_quality_co2 is not None,
        update_key="airquality_co2_density",
        value_fn=lambda device: device.air_quality_co2,
        instance_check=AirQuality,
        name_suffix="CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    DeconzSensorDescription[AirQuality](
        key="air_quality_pm2_5",
        supported_fn=lambda device: device.pm_2_5 is not None,
        update_key="pm2_5",
        value_fn=lambda device: device.pm_2_5,
        instance_check=AirQuality,
        name_suffix="PM25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    DeconzSensorDescription[CarbonDioxide](
        key="carbon_dioxide",
        supported_fn=lambda device: True,
        update_key="measured_value",
        value_fn=lambda device: device.carbon_dioxide,
        instance_check=CarbonDioxide,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
    ),
    DeconzSensorDescription[Consumption](
        key="consumption",
        supported_fn=lambda device: device.consumption is not None,
        update_key="consumption",
        value_fn=lambda device: device.scaled_consumption,
        instance_check=Consumption,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DeconzSensorDescription[Daylight](
        key="daylight_status",
        supported_fn=lambda device: True,
        update_key="status",
        value_fn=lambda device: DAYLIGHT_STATUS[device.daylight_status],
        instance_check=Daylight,
        icon="mdi:white-balance-sunny",
        entity_registry_enabled_default=False,
    ),
    DeconzSensorDescription[Formaldehyde](
        key="formaldehyde",
        supported_fn=lambda device: True,
        update_key="measured_value",
        value_fn=lambda device: device.formaldehyde,
        instance_check=Formaldehyde,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
    ),
    DeconzSensorDescription[GenericStatus](
        key="status",
        supported_fn=lambda device: device.status is not None,
        update_key="status",
        value_fn=lambda device: device.status,
        instance_check=GenericStatus,
    ),
    DeconzSensorDescription[Humidity](
        key="humidity",
        supported_fn=lambda device: device.humidity is not None,
        update_key="humidity",
        value_fn=lambda device: device.scaled_humidity,
        instance_check=Humidity,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    DeconzSensorDescription[LightLevel](
        key="light_level",
        supported_fn=lambda device: device.light_level is not None,
        update_key="lightlevel",
        value_fn=lambda device: device.scaled_light_level,
        instance_check=LightLevel,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    DeconzSensorDescription[Moisture](
        key="moisture",
        supported_fn=lambda device: device.moisture is not None,
        update_key="moisture",
        value_fn=lambda device: device.scaled_moisture,
        instance_check=Moisture,
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    DeconzSensorDescription[ParticulateMatter](
        key="particulate_matter_pm2_5",
        supported_fn=lambda device: device.measured_value is not None,
        update_key="measured_value",
        value_fn=lambda device: device.measured_value,
        instance_check=ParticulateMatter,
        name_suffix="PM25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    DeconzSensorDescription[Power](
        key="power",
        supported_fn=lambda device: device.power is not None,
        update_key="power",
        value_fn=lambda device: device.power,
        instance_check=Power,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    DeconzSensorDescription[Pressure](
        key="pressure",
        supported_fn=lambda device: device.pressure is not None,
        update_key="pressure",
        value_fn=lambda device: device.pressure,
        instance_check=Pressure,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    DeconzSensorDescription[Temperature](
        key="temperature",
        supported_fn=lambda device: device.temperature is not None,
        update_key="temperature",
        value_fn=lambda device: device.scaled_temperature,
        instance_check=Temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    DeconzSensorDescription[Time](
        key="last_set",
        supported_fn=lambda device: device.last_set is not None,
        update_key="lastset",
        value_fn=lambda device: dt_util.parse_datetime(device.last_set),
        instance_check=Time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    DeconzSensorDescription[SensorResources](
        key="battery",
        supported_fn=lambda device: device.battery is not None,
        update_key="battery",
        value_fn=lambda device: device.battery,
        name_suffix="Battery",
        old_unique_id_suffix="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzSensorDescription[SensorResources](
        key="internal_temperature",
        supported_fn=lambda device: device.internal_temperature is not None,
        update_key="temperature",
        value_fn=lambda device: device.internal_temperature,
        name_suffix="Temperature",
        old_unique_id_suffix="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ sensors."""
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[DOMAIN] = set()

    known_device_entities: dict[str, set[str]] = {
        description.key: set()
        for description in ENTITY_DESCRIPTIONS
        if description.instance_check is None
    }

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add sensor from deCONZ."""
        sensor = hub.api.sensors[sensor_id]
        entities: list[DeconzSensor] = []

        for description in ENTITY_DESCRIPTIONS:
            if description.instance_check and not isinstance(
                sensor, description.instance_check
            ):
                continue

            no_sensor_data = False
            if not description.supported_fn(sensor):
                no_sensor_data = True

            if description.instance_check is None:
                if (
                    sensor.type.startswith("CLIP")
                    or (no_sensor_data and description.key != "battery")
                    or (
                        (unique_id := sensor.unique_id.rpartition("-")[0])
                        in known_device_entities[description.key]
                    )
                ):
                    continue
                known_device_entities[description.key].add(unique_id)
                if no_sensor_data and description.key == "battery":
                    DeconzBatteryTracker(
                        sensor_id, hub, description, async_add_entities
                    )
                    continue

            if no_sensor_data:
                continue

            entities.append(DeconzSensor(sensor, hub, description))

        async_add_entities(entities)

    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors,
    )


class DeconzSensor(DeconzDevice[SensorResources], SensorEntity):
    """Representation of a deCONZ sensor."""

    TYPE = DOMAIN
    entity_description: DeconzSensorDescription

    def __init__(
        self,
        device: SensorResources,
        hub: DeconzHub,
        description: DeconzSensorDescription,
    ) -> None:
        """Initialize deCONZ sensor."""
        self.entity_description = description
        self.unique_id_suffix = description.key
        self._update_key = description.update_key
        if description.name_suffix:
            self._name_suffix = description.name_suffix
        super().__init__(device, hub)

        if (
            self.entity_description.key in PROVIDES_EXTRA_ATTRIBUTES
            and self._update_keys is not None
        ):
            self._update_keys.update({"on", "state"})

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    def extra_state_attributes(self) -> dict[str, bool | float | int | str | None]:
        """Return the state attributes of the sensor."""
        attr: dict[str, bool | float | int | str | None] = {}

        if self.entity_description.key not in PROVIDES_EXTRA_ATTRIBUTES:
            return attr

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.internal_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.internal_temperature

        if isinstance(self._device, Consumption):
            attr[ATTR_POWER] = self._device.power

        elif isinstance(self._device, Daylight):
            attr[ATTR_DAYLIGHT] = self._device.daylight

        elif isinstance(self._device, LightLevel):
            if self._device.dark is not None:
                attr[ATTR_DARK] = self._device.dark

            if self._device.daylight is not None:
                attr[ATTR_DAYLIGHT] = self._device.daylight

        elif isinstance(self._device, Power):
            attr[ATTR_CURRENT] = self._device.current
            attr[ATTR_VOLTAGE] = self._device.voltage

        elif isinstance(self._device, Switch):
            for event in self.hub.events:
                if self._device == event.device:
                    attr[ATTR_EVENT_ID] = event.event_id

        return attr


class DeconzBatteryTracker:
    """Track sensors without a battery state and add entity when battery state exist."""

    def __init__(
        self,
        sensor_id: str,
        hub: DeconzHub,
        description: DeconzSensorDescription,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up tracker."""
        self.sensor = hub.api.sensors[sensor_id]
        self.hub = hub
        self.description = description
        self.async_add_entities = async_add_entities
        self.unsubscribe = self.sensor.subscribe(self.async_update_callback)

    @callback
    def async_update_callback(self) -> None:
        """Update the device's state."""
        if self.description.update_key in self.sensor.changed_keys:
            self.unsubscribe()
            self.async_add_entities(
                [DeconzSensor(self.sensor, self.hub, self.description)]
            )
