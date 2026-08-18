"""Sensor platform for the Ampio integration."""

from typing import override

from ampio_mqtt import AmpioObject, SensorKind

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmpioConfigEntry, AmpioData
from .entity import AmpioEntity, eligible_objects

PARALLEL_UPDATES = 0

# Descriptions for the sensor kinds the library can classify, keyed by
# ``SensorKind.key``. Objects classified into any other kind are not exposed.
SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    description.key: description
    for description in (
        SensorEntityDescription(
            key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="pressure_abs",
            translation_key="pressure_abs",
            device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            native_unit_of_measurement=UnitOfPressure.HPA,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="pressure_rel",
            translation_key="pressure_rel",
            device_class=SensorDeviceClass.PRESSURE,
            native_unit_of_measurement=UnitOfPressure.HPA,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="loudness",
            translation_key="loudness",
            device_class=SensorDeviceClass.SOUND_PRESSURE,
            native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            native_unit_of_measurement=LIGHT_LUX,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        SensorEntityDescription(
            key="iaq",
            device_class=SensorDeviceClass.AQI,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        SensorEntityDescription(
            key="co2",
            translation_key="co2",
            device_class=SensorDeviceClass.CO2,
            native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmpioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ampio sensors from the discovery-time object catalogue."""
    data = entry.runtime_data
    entities: list[AmpioSensor] = []
    for obj in eligible_objects(data.client):
        if not isinstance(kind := obj.kind, SensorKind):
            continue
        if (description := SENSOR_DESCRIPTIONS.get(kind.key)) is None:
            continue
        entities.append(AmpioSensor(data, obj, description))
    async_add_entities(entities)


class AmpioSensor(AmpioEntity, SensorEntity):
    """A sensor backed by an Ampio object."""

    def __init__(
        self,
        data: AmpioData,
        obj: AmpioObject,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data, obj)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """The current reading, or None when missing or non-numeric."""
        if (obj := self._object) is None:
            return None
        return obj.numeric_value
