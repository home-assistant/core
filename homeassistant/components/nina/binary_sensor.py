"""NINA binary sensor platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
)
from .coordinator import NinaConfigEntry, NINADataUpdateCoordinator
from .entity import NinaEntity


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: NinaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entries."""

    coordinator = config_entry.runtime_data

    regions: dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    async_add_entities(
        NINAMessage(coordinator, ent, regions[ent], i + 1)
        for ent in coordinator.data
        for i in range(message_slots)
    )


PARALLEL_UPDATES = 0


class NINAMessage(NinaEntity, BinarySensorEntity):
    """Representation of an NINA warning."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, region, region_name, slot_id)

        self._attr_translation_key = "warning"
        self._attr_unique_id = f"{region}-{slot_id}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        if self._active_warning_count <= self._warning_index:
            return False

        return self._get_warning_data().is_valid

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes of the sensor."""
        if not self.is_on:
            return {}

        data = self._get_warning_data()

        return {
            ATTR_HEADLINE: data.headline,  # Deprecated, remove in 2026.08
            ATTR_DESCRIPTION: data.description,  # Deprecated, remove in 2026.08
            ATTR_SENDER: data.sender,  # Deprecated, remove in 2026.08
            ATTR_SEVERITY: data.severity,  # Deprecated, remove in 2026.08
            ATTR_RECOMMENDED_ACTIONS: data.recommended_actions,  # Deprecated, remove in 2026.08
            ATTR_AFFECTED_AREAS: data.affected_areas,  # Deprecated, remove in 2026.08
            ATTR_WEB: data.more_info_url,  # Deprecated, remove in 2026.08
            ATTR_ID: data.id,
            ATTR_SENT: data.sent,
            ATTR_START: data.start,
            ATTR_EXPIRES: data.expires,
        }

    def get_description(self) -> str | None:
        """Return the description."""
        if not self.is_on:
            return None

        return self._get_warning_data().description

    def get_full_affected_areas(self) -> str | None:
        """Return full affected areas."""
        if not self.is_on:
            return None

        return self._get_warning_data().affected_areas

    def get_recommended_actions(self) -> str | None:
        """Return the recommended actions."""
        if not self.is_on:
            return None

        return self._get_warning_data().recommended_actions
