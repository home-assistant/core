"""Matter sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from chip.clusters import Objects as clusters
from chip.clusters.Types import Nullable, NullValue
from matter_server.client.models import device_types

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescriptionBaseClass
from .helpers import get_matter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter sensors from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SENSOR, async_add_entities)


class MatterSensor(MatterEntity, SensorEntity):
    """Representation of a Matter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    entity_description: MatterSensorEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        measurement: Nullable | float | None
        measurement = self.get_matter_attribute_value(
            # We always subscribe to a single value
            self.entity_description.subscribe_attributes[0],
        )

        if measurement == NullValue or measurement is None:
            measurement = None
        else:
            measurement = self.entity_description.measurement_to_ha(measurement)

        self._attr_native_value = measurement


@dataclass
class MatterSensorEntityDescriptionMixin:
    """Required fields for sensor device mapping."""

    measurement_to_ha: Callable[[float], float]


@dataclass
class MatterSensorEntityDescription(
    SensorEntityDescription,
    MatterEntityDescriptionBaseClass,
    MatterSensorEntityDescriptionMixin,
):
    """Matter Sensor entity description."""


# You can't set default values on inherited data classes
MatterSensorEntityDescriptionFactory = partial(
    MatterSensorEntityDescription, entity_cls=MatterSensor
)


DEVICE_ENTITY: dict[
    type[device_types.DeviceType],
    MatterEntityDescriptionBaseClass | list[MatterEntityDescriptionBaseClass],
] = {
    device_types.TemperatureSensor: MatterSensorEntityDescriptionFactory(
        key=device_types.TemperatureSensor,
        name="Temperature",
        measurement_to_ha=lambda x: x / 100,
        subscribe_attributes=(
            clusters.TemperatureMeasurement.Attributes.MeasuredValue,
        ),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    device_types.PressureSensor: MatterSensorEntityDescriptionFactory(
        key=device_types.PressureSensor,
        name="Pressure",
        measurement_to_ha=lambda x: x / 10,
        subscribe_attributes=(clusters.PressureMeasurement.Attributes.MeasuredValue,),
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    device_types.FlowSensor: MatterSensorEntityDescriptionFactory(
        key=device_types.FlowSensor,
        name="Flow",
        measurement_to_ha=lambda x: x / 10,
        subscribe_attributes=(clusters.FlowMeasurement.Attributes.MeasuredValue,),
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    device_types.HumiditySensor: MatterSensorEntityDescriptionFactory(
        key=device_types.HumiditySensor,
        name="Humidity",
        measurement_to_ha=lambda x: x / 100,
        subscribe_attributes=(
            clusters.RelativeHumidityMeasurement.Attributes.MeasuredValue,
        ),
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    device_types.LightSensor: MatterSensorEntityDescriptionFactory(
        key=device_types.LightSensor,
        name="Light",
        measurement_to_ha=lambda x: round(pow(10, ((x - 1) / 10000)), 1),
        subscribe_attributes=(
            clusters.IlluminanceMeasurement.Attributes.MeasuredValue,
        ),
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
}
