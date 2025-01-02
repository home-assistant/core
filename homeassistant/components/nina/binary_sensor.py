"""NINA sensor platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AFFECTED_AREAS,
    ATTR_DESCRIPTION,
    ATTR_EXPIRES,
    ATTR_HEADLINE,
    ATTR_ID,
    ATTR_RECOMMENDED_ACTIONS,
    ATTR_SENDER,
    ATTR_SENT,
    ATTR_SEVERITY,
    ATTR_START,
    ATTR_WEB,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
)
from .coordinator import NINADataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entries."""

    coordinator: NINADataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    regions: dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    async_add_entities(
        NINAMessage(coordinator, ent, regions[ent], i + 1, config_entry)
        for ent in coordinator.data
        for i in range(message_slots)
    )


class NINAMessage(CoordinatorEntity[NINADataUpdateCoordinator], BinarySensorEntity):
    """Representation of an NINA warning."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._region = region
        self._warning_index = slot_id - 1

        self._attr_name = f"Warning: {region_name} {slot_id}"
        self._attr_unique_id = f"{region}-{slot_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="NINA",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        if len(self.coordinator.data[self._region]) <= self._warning_index:
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
            ATTR_RECOMMENDED_ACTIONS: data.recommended_actions,
            ATTR_AFFECTED_AREAS: data.affected_areas,
            ATTR_WEB: data.web,
            ATTR_ID: data.id,
            ATTR_SENT: data.sent,
            ATTR_START: data.start,
            ATTR_EXPIRES: data.expires,
        }
