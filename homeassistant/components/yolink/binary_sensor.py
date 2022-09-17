"""YoLink BinarySensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
    ATTR_COORDINATORS,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    DOMAIN,
)
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """YoLink BinarySensorEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    state_key: str = "state"
    value: Callable[[Any], bool | None] = lambda _: None


SENSOR_DEVICE_TYPE = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
]


def is_door_sensor(device: YoLinkDevice) -> bool:
    """Check Door Sensor type."""
    return device.device_type == ATTR_DEVICE_DOOR_SENSOR and (
        device.parent_id is None or device.parent_id == "null"
    )


SENSOR_TYPES: tuple[YoLinkBinarySensorEntityDescription, ...] = (
    YoLinkBinarySensorEntityDescription(
        key="door_state",
        icon="mdi:door",
        device_class=BinarySensorDeviceClass.DOOR,
        name="State",
        value=lambda value: value == "open" if value is not None else None,
        exists_fn=is_door_sensor,
    ),
    YoLinkBinarySensorEntityDescription(
        key="motion_state",
        device_class=BinarySensorDeviceClass.MOTION,
        name="Motion",
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MOTION_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="leak_state",
        name="Leak",
        icon="mdi:water",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_LEAK_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="vibration_state",
        name="Vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_VIBRATION_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="co_detected",
        name="Co Detected",
        device_class=BinarySensorDeviceClass.CO,
        value=lambda state: state.get("gasAlarm"),
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_CO_SMOKE_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="smoke_detected",
        name="Smoke Detected",
        device_class=BinarySensorDeviceClass.SMOKE,
        value=lambda state: state.get("smokeAlarm"),
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_CO_SMOKE_SENSOR,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATORS]
    binary_sensor_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in SENSOR_DEVICE_TYPE
    ]
    entities = []
    for binary_sensor_device_coordinator in binary_sensor_device_coordinators:
        for description in SENSOR_TYPES:
            if description.exists_fn(binary_sensor_device_coordinator.device):
                entities.append(
                    YoLinkBinarySensorEntity(
                        config_entry, binary_sensor_device_coordinator, description
                    )
                )
    async_add_entities(entities)


class YoLinkBinarySensorEntity(YoLinkEntity, BinarySensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkBinarySensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkBinarySensorEntityDescription,
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
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        self._attr_is_on = self.entity_description.value(
            state.get(self.entity_description.state_key)
        )
        self.async_write_ha_state()
