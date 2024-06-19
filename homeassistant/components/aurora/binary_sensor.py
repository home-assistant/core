"""Support for Aurora Forecast binary sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AuroraConfigEntry
from .entity import AuroraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AuroraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        [
            AuroraSensor(
                coordinator=entry.runtime_data,
                translation_key="visibility_alert",
            )
        ]
    )


class AuroraSensor(AuroraEntity, BinarySensorEntity):
    """Implementation of an aurora sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if aurora is visible."""
        return self.coordinator.data > self.coordinator.threshold
