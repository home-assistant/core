"""NINA sensor platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NINADataUpdateCoordinator
from .const import (
    ATTR_DESCRIPTION,
    ATTR_EXPIRES,
    ATTR_HEADLINE,
    ATTR_ID,
    ATTR_SENDER,
    ATTR_SENT,
    ATTR_SEVERITY,
    ATTR_START,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entries."""

    coordinator: NINADataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    regions: dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    entities: list[NINAMessage] = []

    for ent in coordinator.data:
        for i in range(0, message_slots):
            entities.append(NINAMessage(coordinator, ent, regions[ent], i + 1))

    async_add_entities(entities)


class NINAMessage(CoordinatorEntity[NINADataUpdateCoordinator], BinarySensorEntity):
    """Representation of an NINA warning."""

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._region: str = region
        self._warning_index: int = slot_id - 1

        self._attr_name: str = f"Warning: {region_name} {slot_id}"
        self._attr_unique_id: str = f"{region}-{slot_id}"
        self._attr_device_class: str = BinarySensorDeviceClass.SAFETY

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        if not len(self.coordinator.data[self._region]) > self._warning_index:
            return False

        data = self.coordinator.data[self._region][self._warning_index]

        return data.is_valid

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes of the sensor."""
        if not self.is_on:
            return {}

        data = self.coordinator.data[self._region][self._warning_index]

        return {
            ATTR_HEADLINE: data.headline,
            ATTR_DESCRIPTION: data.description,
            ATTR_SENDER: data.sender,
            ATTR_SEVERITY: data.severity,
            ATTR_ID: data.id,
            ATTR_SENT: data.sent,
            ATTR_START: data.start,
            ATTR_EXPIRES: data.expires,
        }
