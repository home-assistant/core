"""Ecovacs device_tracker entities (mower position)."""

from __future__ import annotations

from math import cos, radians

from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.events import PositionsEvent
from deebot_client.events.map import PositionType

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsEntity

# Approximation: 1° of latitude is ~111.32 km. Good enough for a single
# garden where the rover stays within ~100 m of the dock; the small
# error introduced near the poles is irrelevant at this scale.
_M_PER_DEG_LAT = 111_320.0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add ecovacs device_tracker entities (one per mower with a position capability)."""
    controller = config_entry.runtime_data
    trackers: list[EcovacsMowerTracker] = [
        EcovacsMowerTracker(device, hass)
        for device in controller.devices
        if device.capabilities.position is not None
    ]
    if trackers:
        async_add_entities(trackers)


class EcovacsMowerTracker(EcovacsEntity[Capabilities], TrackerEntity):
    """Mower GPS tracker derived from PositionsEvent.

    Mower coordinates (`deebotPos.x` / `y`, in centimetres relative to
    the dock) are converted to latitude/longitude using the Home
    Assistant home zone as the dock anchor. The mower's local frame is
    assumed to be north-aligned (no rotation correction yet); a future
    follow-up can expose the dock anchor and orientation as config
    options for non-default setups.
    """

    _attr_translation_key = "position"
    _attr_source_type = SourceType.GPS

    entity_description = EntityDescription(key="position")

    def __init__(self, device: Device, hass: HomeAssistant) -> None:
        """Initialize the tracker."""
        super().__init__(device, device.capabilities)
        self._anchor_lat: float = hass.config.latitude
        self._anchor_lng: float = hass.config.longitude
        self._lat: float | None = None
        self._lng: float | None = None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._lat

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._lng

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_positions(event: PositionsEvent) -> None:
            mower_pos = next(
                (p for p in event.positions if p.type is PositionType.DEEBOT),
                None,
            )
            if mower_pos is None:
                return

            # Mower frame: x = East offset (cm), y = North offset (cm).
            delta_east_m = mower_pos.x / 100.0
            delta_north_m = mower_pos.y / 100.0

            self._lat = self._anchor_lat + (delta_north_m / _M_PER_DEG_LAT)
            self._lng = self._anchor_lng + (
                delta_east_m / (_M_PER_DEG_LAT * cos(radians(self._anchor_lat)))
            )
            self.async_write_ha_state()

        self._subscribe(self._capability.position.event, on_positions)
