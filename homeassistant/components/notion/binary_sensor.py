"""Support for Notion binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
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
    SENSOR_WINDOW_HINGED_HORIZONTAL,
    SENSOR_WINDOW_HINGED_VERTICAL,
)


@dataclass
class NotionBinarySensorDescriptionMixin:
    """Define an entity description mixin for binary and regular sensors."""

    on_state: Literal["alarm", "critical", "leak", "not_missing", "open"]


@dataclass
class NotionBinarySensorDescription(
    BinarySensorEntityDescription, NotionBinarySensorDescriptionMixin
):
    """Describe a Notion binary sensor."""


BINARY_SENSOR_DESCRIPTIONS = (
    NotionBinarySensorDescription(
        key=SENSOR_BATTERY,
        name="Low Battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state="critical",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_DOOR,
        name="Door",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="open",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_GARAGE_DOOR,
        name="Garage Door",
        device_class=BinarySensorDeviceClass.GARAGE_DOOR,
        on_state="open",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_LEAK,
        name="Leak Detector",
        device_class=BinarySensorDeviceClass.MOISTURE,
        on_state="leak",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_MISSING,
        name="Missing",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state="not_missing",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_SAFE,
        name="Safe",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="open",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_SLIDING,
        name="Sliding Door/Window",
        device_class=BinarySensorDeviceClass.DOOR,
        on_state="open",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_SMOKE_CO,
        name="Smoke/Carbon Monoxide Detector",
        device_class=BinarySensorDeviceClass.SMOKE,
        on_state="alarm",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_WINDOW_HINGED_HORIZONTAL,
        name="Hinged Window",
        device_class=BinarySensorDeviceClass.WINDOW,
        on_state="open",
    ),
    NotionBinarySensorDescription(
        key=SENSOR_WINDOW_HINGED_VERTICAL,
        name="Hinged Window",
        device_class=BinarySensorDeviceClass.WINDOW,
        on_state="open",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NotionBinarySensor(
                coordinator,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                description,
            )
            for task_id, task in coordinator.data["tasks"].items()
            for description in BINARY_SENSOR_DESCRIPTIONS
            if description.key == task["task_type"]
            and (sensor := coordinator.data["sensors"][task["sensor_id"]])
        ]
    )


class NotionBinarySensor(NotionEntity, BinarySensorEntity):
    """Define a Notion sensor."""

    entity_description: NotionBinarySensorDescription

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        task = self.coordinator.data["tasks"][self._task_id]

        if "value" in task["status"]:
            state = task["status"]["value"]
        elif task["status"].get("insights", {}).get("primary"):
            state = task["status"]["insights"]["primary"]["to_state"]
        else:
            LOGGER.warning("Unknown data payload: %s", task["status"])
            state = None

        self._attr_is_on = self.entity_description.on_state == state
