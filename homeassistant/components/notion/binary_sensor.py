"""Support for Notion binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aionotion.listener.models import ListenerKind

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NotionEntity
from .const import (
    DOMAIN,
    LOGGER,
    SENSOR_BATTERY,
    SENSOR_DOOR,
    SENSOR_GARAGE_DOOR,
    SENSOR_LEAK,
    SENSOR_MISSING,
    SENSOR_SAFE,
    SENSOR_SLIDING,
    SENSOR_SMOKE_CO,
    SENSOR_WINDOW_HINGED,
)
from .coordinator import NotionDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class NotionBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Notion binary sensor."""

    on_state: Literal["alarm", "leak", "low", "not_missing", "open"]


BINARY_SENSOR_DESCRIPTIONS: dict[ListenerKind, NotionBinarySensorDescription] = {
    ListenerKind.BATTERY: NotionBinarySensorDescription(
        key=SENSOR_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state="low",
    ),
    ListenerKind.DOOR: NotionBinarySensorDescription(
        key=SENSOR_DOOR,
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="open",
    ),
    ListenerKind.GARAGE_DOOR: NotionBinarySensorDescription(
        key=SENSOR_GARAGE_DOOR,
        device_class=BinarySensorDeviceClass.GARAGE_DOOR,
        on_state="open",
    ),
    ListenerKind.LEAK: NotionBinarySensorDescription(
        key=SENSOR_LEAK,
        device_class=BinarySensorDeviceClass.MOISTURE,
        on_state="leak",
    ),
    ListenerKind.SENSOR_CONNECTION: NotionBinarySensorDescription(
        key=SENSOR_MISSING,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state="not_missing",
    ),
    ListenerKind.SAFE: NotionBinarySensorDescription(
        key=SENSOR_SAFE,
        translation_key="safe",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="open",
    ),
    ListenerKind.SLIDING_DOOR_OR_WINDOW: NotionBinarySensorDescription(
        key=SENSOR_SLIDING,
        translation_key="sliding_door_window",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="open",
    ),
    ListenerKind.ALARM: NotionBinarySensorDescription(
        key=SENSOR_SMOKE_CO,
        translation_key="smoke_carbon_monoxide_detector",
        device_class=BinarySensorDeviceClass.SMOKE,
        on_state="alarm",
    ),
    ListenerKind.WINDOW_HINGED_VERTICAL: NotionBinarySensorDescription(
        key=SENSOR_WINDOW_HINGED,
        translation_key="hinged_window",
        on_state="open",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator: NotionDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NotionBinarySensor(
                coordinator, listener.id, sensor.uuid, sensor.bridge.id, description
            )
            for listener in coordinator.data.listeners.values()
            if (description := BINARY_SENSOR_DESCRIPTIONS.get(listener.kind))
            and (sensor := coordinator.data.sensors.get(listener.sensor_id))
        ]
    )


class NotionBinarySensor(NotionEntity, BinarySensorEntity):
    """Define a Notion sensor."""

    entity_description: NotionBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.listener.insights.primary.value:
            LOGGER.warning("Unknown listener structure: %s", self.listener)
            return False
        return self.listener.insights.primary.value == self.entity_description.on_state
