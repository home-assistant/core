"""YoLink BinarySensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.const import (
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR,
)
from yolink.device import YoLinkDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YoLinkLocalCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True, kw_only=True)
class YoLinkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """YoLink BinarySensorEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    should_update_entity: Callable = lambda state: True
    value: Callable[[YoLinkDevice, dict], bool | None]
    is_available: Callable[[YoLinkDevice, dict], bool] = lambda _, __: True


def parse_data_leak_sensor_state(device: YoLinkDevice, data: dict) -> bool | None:
    """Parse leak sensor state."""
    if device.device_type == ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR:
        if (state := data.get("state")) is None or (
            value := state.get("waterDetection")
        ) is None:
            return None
        return (
            value == "normal"
            if data.get("waterDetectionMode") == "WaterPeak"
            else value == "leak"
        )
    return data.get("state") in ["alert", "full"]


def is_leak_sensor_state_available(device: YoLinkDevice, data: dict) -> bool:
    """Check leak sensor state availability."""
    if device.device_type == ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR:
        if (
            (alarms := data.get("alarm")) is not None
            and isinstance(alarms, list)
            and "Alert.DetectorError" in alarms
        ):
            return False
    if (alarms := data.get("alarmState")) is not None and alarms.get(
        "detectorError"
    ) is True:
        return False
    return True


BINARY_SENSOR_DESCRIPTIONS: tuple[YoLinkBinarySensorEntityDescription, ...] = (
    YoLinkBinarySensorEntityDescription(
        key="leak_state",
        device_class=BinarySensorDeviceClass.MOISTURE,
        exists_fn=lambda device: (
            device.device_type
            in [ATTR_DEVICE_LEAK_SENSOR, ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR]
        ),
        value=parse_data_leak_sensor_state,
        is_available=is_leak_sensor_state_available,
    ),
    YoLinkBinarySensorEntityDescription(
        key="motion_state",
        device_class=BinarySensorDeviceClass.MOTION,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MOTION_SENSOR,
        value=lambda device, data: (
            value == "alert" if (value := data.get("state")) is not None else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sensor from a config entry."""
    coordinators: dict[str, YoLinkLocalCoordinator] = config_entry.runtime_data[1]
    binary_sensor_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if coordinator.device.device_type
        in [ATTR_DEVICE_LEAK_SENSOR, ATTR_DEVICE_MOTION_SENSOR]
    ]
    async_add_entities(
        YoLinkBinarySensorEntity(config_entry, binary_sensor_coordinator, description)
        for binary_sensor_coordinator in binary_sensor_coordinators
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.exists_fn(binary_sensor_coordinator.device)
    )


class YoLinkBinarySensorEntity(YoLinkEntity, BinarySensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkBinarySensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkLocalCoordinator,
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
        if (
            _attr_val := self.entity_description.value(self.coordinator.device, state)
        ) is None or self.entity_description.should_update_entity(_attr_val) is False:
            return
        _is_attr_available = self.entity_description.is_available(
            self.coordinator.device, state
        )
        self._attr_available = _is_attr_available
        self._attr_is_on = _attr_val if _is_attr_available else None
        self.async_write_ha_state()
