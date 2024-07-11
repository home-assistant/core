"""YoLink BinarySensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.const import (
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
)
from yolink.device import YoLinkDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True)
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


SENSOR_TYPES: tuple[YoLinkBinarySensorEntityDescription, ...] = (
    YoLinkBinarySensorEntityDescription(
        key="door_state",
        device_class=BinarySensorDeviceClass.DOOR,
        value=lambda value: value == "open" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_DOOR_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="motion_state",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MOTION_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="leak_state",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value=lambda value: value in ("alert", "full") if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_LEAK_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="vibration_state",
        device_class=BinarySensorDeviceClass.VIBRATION,
        value=lambda value: value == "alert" if value is not None else None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_VIBRATION_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="co_detected",
        device_class=BinarySensorDeviceClass.CO,
        value=lambda state: state.get("gasAlarm"),
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_CO_SMOKE_SENSOR,
    ),
    YoLinkBinarySensorEntityDescription(
        key="smoke_detected",
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
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    binary_sensor_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in SENSOR_DEVICE_TYPE
    ]
    async_add_entities(
        YoLinkBinarySensorEntity(
            config_entry, binary_sensor_device_coordinator, description
        )
        for binary_sensor_device_coordinator in binary_sensor_device_coordinators
        for description in SENSOR_TYPES
        if description.exists_fn(binary_sensor_device_coordinator.device)
    )


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

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        self._attr_is_on = self.entity_description.value(
            state.get(self.entity_description.state_key)
        )
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return true is device is available."""
        return super().available and self.coordinator.dev_online
