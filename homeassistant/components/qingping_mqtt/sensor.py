"""Support for Qingping sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_MAC, CONF_MODEL, UnitOfRatio, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QingpingMqttConfigEntry
from .const import MODELS
from .coordinator import QingpingMqttCoordinator


@dataclass(frozen=True, kw_only=True)
class QingpingMqttSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor of a Qingping device connected via MQTT."""

    value_fn: Callable[[dict[str, Any]], StateType]


def _sensor_value(
    field: str,
) -> Callable[[dict[str, Any]], StateType]:
    """Return a value function reading a decoded sensor field."""
    return lambda data: data["sensors"].get(field)


SENSOR_DESCRIPTIONS: Final[
    dict[str, tuple[QingpingMqttSensorEntityDescription, ...]]
] = {
    "cgr1w": (
        QingpingMqttSensorEntityDescription(
            key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=_sensor_value("temperature"),
        ),
        QingpingMqttSensorEntityDescription(
            key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=_sensor_value("humidity"),
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QingpingMqttConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qingping MQTT sensors."""
    coordinator = entry.runtime_data
    mac = entry.data[CONF_MAC]
    model = entry.data[CONF_MODEL]
    async_add_entities(
        QingpingMqttSensor(coordinator, description, mac, model)
        for description in SENSOR_DESCRIPTIONS[model]
    )


class QingpingMqttSensor(CoordinatorEntity[QingpingMqttCoordinator], SensorEntity):
    """Representation of a sensor of a Qingping device connected via MQTT."""

    entity_description: QingpingMqttSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QingpingMqttCoordinator,
        description: QingpingMqttSensorEntityDescription,
        mac: str,
        model: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="Qingping",
            model=MODELS[model],
            name=MODELS[model],
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the device has not been marked offline."""
        return self.coordinator.last_update_success and self.coordinator.data["online"]

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)
