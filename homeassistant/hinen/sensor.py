"""Support for Hinen Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from config.custom_components.hinen.enum import DeviceAlertStatus, DeviceStatus
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ATTR_ALERT_STATUS, ATTR_DEVICE_NAME, ATTR_STATUS, COORDINATOR, DOMAIN
from .coordinator import HinenDataUpdateCoordinator
from .entity import HinenDeviceEntity


@dataclass(frozen=True, kw_only=True)
class HinenSensorEntityDescription(SensorEntityDescription):
    """Describes Hinen sensor entity."""

    available_fn: Callable[[Any], bool]
    value_fn: Callable[[Any], StateType]
    # entity_picture_fn: Callable[[Any], str | None]
    # attributes_fn: Callable[[Any], dict[str, Any] | None] | None


SENSOR_TYPES = [
    HinenSensorEntityDescription(
        key="status",
        translation_key="status",
        available_fn=lambda device_detail: device_detail[ATTR_DEVICE_NAME] is not None,
        value_fn=lambda device_detail: DeviceStatus.get_display_name(
            device_detail[ATTR_STATUS]
        ),
    ),
    HinenSensorEntityDescription(
        key="alert_status",
        translation_key="alert_status",
        available_fn=lambda device_detail: device_detail[ATTR_SERIAL_NUMBER]
        is not None,
        value_fn=lambda device_detail: DeviceAlertStatus.get_display_name(
            device_detail[ATTR_ALERT_STATUS]
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hinen sensor."""
    coordinator: HinenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    # hinen_open: HinenOpen = hass.data[DOMAIN][entry.entry_id][AUTH].hinen_open
    entities: list = [
        HinenSensor(coordinator, sensor_type, device_id)
        for device_id in coordinator.data
        for sensor_type in SENSOR_TYPES
    ]

    async_add_entities(entities)


class HinenSensor(HinenDeviceEntity, SensorEntity):
    """Representation of a Hinen sensor."""

    entity_description: HinenSensorEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data[self._device_id]
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._device_id])

    # @property
    # def entity_picture(self) -> str | None:
    #     """Return the value reported by the sensor."""
    #     if not self.available:
    #         return None
    #     return self.entity_description.entity_picture_fn(
    #         self.coordinator.data[self._channel_id]
    #     )

    # @property
    # def extra_state_attributes(self) -> dict[str, Any] | None:
    #     """Return the extra state attributes."""
    #     if self.entity_description.attributes_fn:
    #         return self.entity_description.attributes_fn(
    #             self.coordinator.data[self._channel_id]
    #         )
    #     return None
