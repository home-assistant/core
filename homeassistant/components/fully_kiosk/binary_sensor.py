"""Fully Kiosk Browser sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity

SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="kioskMode",
        translation_key="kiosk_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="plugged",
        translation_key="plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="isDeviceAdmin",
        translation_key="device_admin",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser sensor."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        FullyBinarySensor(coordinator, description)
        for description in SENSORS
        if description.key in coordinator.data
    )


class FullyBinarySensor(FullyKioskEntity, BinarySensorEntity):
    """Representation of a Fully Kiosk Browser binary sensor."""

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return if the binary sensor is on."""
        if (value := self.coordinator.data.get(self.entity_description.key)) is None:
            return None
        return bool(value)
