"""Cover platform for Actron Air integration."""

from typing import override

from actron_neo_api import ActronAirZone

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirZoneEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air cover entities."""
    system_coordinators = entry.runtime_data.system_coordinators

    async_add_entities(
        ActronAirZoneDamper(coordinator, zone)
        for coordinator in system_coordinators.values()
        for zone in coordinator.data.remote_zone_info
        if zone.exists
    )


class ActronAirZoneDamper(ActronAirZoneEntity, CoverEntity):
    """Representation of the damper of an Actron Air zone."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_translation_key = "damper"
    # The damper is read-only; CoverEntity infers movement features when unset.
    _attr_supported_features = CoverEntityFeature(0)

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        zone: ActronAirZone,
    ) -> None:
        """Initialize the damper."""
        super().__init__(coordinator, zone)
        self._attr_unique_id = f"{self._zone_identifier}_damper"

    @property
    @override
    def current_cover_position(self) -> int:
        """Return how far the damper is open, from 0 to 100."""
        return round(self._zone.zone_position)

    @property
    @override
    def is_closed(self) -> bool:
        """Return True if the damper is fully closed."""
        return self.current_cover_position == 0
