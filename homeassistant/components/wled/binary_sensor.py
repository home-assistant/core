"""Support for WLED binary sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .models import WLEDEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a WLED binary sensor based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WLEDUpdateBinarySensor(coordinator),
        ]
    )


class WLEDUpdateBinarySensor(WLEDEntity, BinarySensorEntity):
    """Defines a WLED firmware binary sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_translation_key = "firmware"

    # Disabled by default, as this entity is deprecated.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_update"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        current = self.coordinator.data.info.version
        beta = self.coordinator.data.info.version_latest_beta
        stable = self.coordinator.data.info.version_latest_stable

        return current is not None and (
            (stable is not None and stable > current)
            or (
                beta is not None
                and (current.alpha or current.beta or current.release_candidate)
                and beta > current
            )
        )
