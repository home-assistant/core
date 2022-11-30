"""YoLink Binary Sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.device import YoLinkDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import percentage

from .const import (
    ATTR_COORDINATORS,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    DOMAIN,
)
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkSensorEntityDescriptionMixin:
    """Mixin for device type."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True


@dataclass
class YoLinkSensorEntityDescription(
    YoLinkSensorEntityDescriptionMixin, SensorEntityDescription
):
    """YoLink SensorEntityDescription."""

    value: Callable = lambda state: state


SENSOR_DEVICE_TYPE = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
]

BATTERY_POWER_SENSOR = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
]


def cvt_battery(val: int | None) -> int | None:
    """Convert battery to percentage."""
    if val is None:
        return None
    if val > 0:
        return percentage.ordered_list_item_to_percentage([1, 2, 3, 4], val)
    return 0


SENSOR_TYPES: tuple[YoLinkSensorEntityDescription, ...] = (
    YoLinkSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
        value=cvt_battery,
        exists_fn=lambda device: device.device_type in BATTERY_POWER_SENSOR,
    ),
    YoLinkSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        name="Humidity",
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_TH_SENSOR],
    ),
    YoLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_TH_SENSOR],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATORS]
    sensor_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in SENSOR_DEVICE_TYPE
    ]
    entities = []
    for sensor_device_coordinator in sensor_device_coordinators:
        for description in SENSOR_TYPES:
            if description.exists_fn(sensor_device_coordinator.device):
                entities.append(
                    YoLinkSensorEntity(
                        config_entry,
                        sensor_device_coordinator,
                        description,
                    )
                )
    async_add_entities(entities)


class YoLinkSensorEntity(YoLinkEntity, SensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkSensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkSensorEntityDescription,
    ) -> None:
        """Init YoLink Sensor."""
        super().__init__(config_entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )
        self._attr_name = (
            f"{coordinator.device.device_name} ({self.entity_description.name})"
        )

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        self._attr_native_value = self.entity_description.value(
            state.get(self.entity_description.key)
        )
        self.async_write_ha_state()
