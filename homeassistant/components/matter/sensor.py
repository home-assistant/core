"""Matter sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from chip.clusters.Types import Nullable, NullValue
from matter_server.common.models import device_types
from matter_server.common.models.device_type_instance import MatterDeviceTypeInstance

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
    VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
    Platform,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MatterEntity, MatterEntityDescriptionBaseClass

if TYPE_CHECKING:
    from .adapter import MatterAdapter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter sensors from Config Entry."""
    matter: MatterAdapter = hass.data[DOMAIN][config_entry.entry_id]
    matter.register_platform_handler(Platform.SENSOR, async_add_entities)


class MatterSensor(MatterEntity, SensorEntity):
    """Representation of a Matter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    entity_description: MatterSensorEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        measurement: Nullable | float | None
        measurement = _get_attribute_value(
            self._device_type_instance,
            # We always subscribe to a single value
            self.entity_description.subscribe_attributes[0],
        )

        if measurement is NullValue or measurement is None:
            measurement = None
        else:
            measurement = self.entity_description.measurement_to_ha(measurement)

        self._attr_native_value = measurement


def _get_attribute_value(
    device_type_instance: MatterDeviceTypeInstance,
    attribute: clusters.ClusterAttributeDescriptor,
) -> Any:
    """Return the value of an attribute."""
    # Find the cluster for this attribute. We don't have a lookup table yet.
    cluster_cls: clusters.Cluster = next(
        cluster
        for cluster in device_type_instance.device_type.clusters
        if cluster.id == attribute.cluster_id
    )

    # Find the attribute descriptor so we know the instance variable to fetch
    attribute_descriptor: clusters.ClusterObjectFieldDescriptor = next(
        descriptor
        for descriptor in cluster_cls.descriptor.Fields
        if descriptor.Tag == attribute.attribute_id
    )

    cluster_data = device_type_instance.get_cluster(cluster_cls)
    return getattr(cluster_data, attribute_descriptor.Label)


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
        native_unit_of_measurement=VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
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
