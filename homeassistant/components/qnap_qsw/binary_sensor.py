"""Support for the QNAP QSW binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from aioqsw.const import QSD_ANOMALY, QSD_FIRMWARE_CONDITION, QSD_MESSAGE

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MESSAGE, DOMAIN
from .coordinator import QswUpdateCoordinator
from .entity import QswEntityDescription, QswSensorEntity


@dataclass
class QswBinarySensorEntityDescription(
    BinarySensorEntityDescription, QswEntityDescription
):
    """A class that describes QNAP QSW binary sensor entities."""

    attributes: dict[str, list[str]] | None = None


BINARY_SENSOR_TYPES: Final[tuple[QswBinarySensorEntityDescription, ...]] = (
    QswBinarySensorEntityDescription(
        attributes={
            ATTR_MESSAGE: [QSD_FIRMWARE_CONDITION, QSD_MESSAGE],
        },
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=QSD_FIRMWARE_CONDITION,
        name="Anomaly",
        subkey=QSD_ANOMALY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW binary sensors from a config_entry."""
    coordinator: QswUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        QswBinarySensor(coordinator, description, entry)
        for description in BINARY_SENSOR_TYPES
        if (
            description.key in coordinator.data
            and description.subkey in coordinator.data[description.key]
        )
    )


class QswBinarySensor(QswSensorEntity, BinarySensorEntity):
    """Define a QNAP QSW binary sensor."""

    entity_description: QswBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: QswUpdateCoordinator,
        description: QswBinarySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.product} {description.name}"
        self._attr_unique_id = (
            f"{entry.unique_id}_{description.key}_{description.subkey}"
        )
        self.entity_description = description
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update binary sensor attributes."""
        self._attr_is_on = self.get_device_value(
            self.entity_description.key, self.entity_description.subkey
        )
        super()._async_update_attrs()
