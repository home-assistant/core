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
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import percentage

from .const import ATTR_COORDINATOR, ATTR_DEVICE_DOOR_SENSOR, DOMAIN
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


SENSOR_TYPES: tuple[YoLinkSensorEntityDescription, ...] = (
    YoLinkSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: percentage.ordered_list_item_to_percentage(
            [1, 2, 3, 4], value
        ),
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_DOOR_SENSOR],
    ),
)

SENSOR_DEVICE_TYPE = [ATTR_DEVICE_DOOR_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATOR]
    sensor_devices = [
        device
        for device in coordinator.yl_devices
        if device.device_type in SENSOR_DEVICE_TYPE
    ]
    entities = []
    for sensor_device in sensor_devices:
        for description in SENSOR_TYPES:
            if description.exists_fn(sensor_device):
                entities.append(
                    YoLinkSensorEntity(coordinator, description, sensor_device)
                )
    async_add_entities(entities)


class YoLinkSensorEntity(YoLinkEntity, SensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkSensorEntityDescription

    def __init__(
        self,
        coordinator: YoLinkCoordinator,
        description: YoLinkSensorEntityDescription,
        device: YoLinkDevice,
    ) -> None:
        """Init YoLink Sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id} {self.entity_description.key}"
        self._attr_name = f"{device.device_name} ({self.entity_description.name})"

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        self._attr_native_value = self.entity_description.value(
            state[self.entity_description.key]
        )
        self.async_write_ha_state()
