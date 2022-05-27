"""YoLink BinarySensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.device import YoLinkDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_COORDINATOR,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    DOMAIN,
)
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """YoLink BinarySensorEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    state_key: str = "state"
    value: Callable[[str], bool | None] = lambda _: None


SENSOR_DEVICE_TYPE = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
]

SENSOR_TYPES: tuple[YoLinkBinarySensorEntityDescription, ...] = (
    YoLinkBinarySensorEntityDescription(
        key="door_state",
        icon="mdi:door",
        device_class=BinarySensorDeviceClass.DOOR,
        name="State",
        value=lambda value: value == "open" if value is not None else None,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_DOOR_SENSOR],
    ),
    YoLinkBinarySensorEntityDescription(
        key="motion_state",
        device_class=BinarySensorDeviceClass.MOTION,
        name="Motion",
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_MOTION_SENSOR],
    ),
    YoLinkBinarySensorEntityDescription(
        key="leak_state",
        name="Leak",
        icon="mdi:water",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_LEAK_SENSOR],
    ),
)


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
                    YoLinkBinarySensorEntity(coordinator, description, sensor_device)
                )
    async_add_entities(entities)


class YoLinkBinarySensorEntity(YoLinkEntity, BinarySensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YoLinkCoordinator,
        description: YoLinkBinarySensorEntityDescription,
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
        self._attr_is_on = self.entity_description.value(
            state[self.entity_description.state_key]
        )
        self.async_write_ha_state()
