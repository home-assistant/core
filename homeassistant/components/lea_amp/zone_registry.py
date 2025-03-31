"""Zone Registry."""

import logging

from .zone import LeaZone


# discovered_devices: number of zones
class ZoneRegistry:
    """Zone Registry Class."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Init."""
        self._num_of_zones: dict[int, LeaZone] = {}
        self._custom_zones_queue: set[int] = set()
        self._logger = logger or logging.getLogger(__name__)

    def add_discovered_zone(self, zone: LeaZone) -> LeaZone:
        """Add Discovered Zones."""
        if int(zone.zone_id) in self._custom_zones_queue:
            self._logger.debug(
                f"Found manullay added device {zone}. Removing from queue."  # noqa: G004
            )
            self._custom_zones_queue.remove(int(zone.zone_id))
            zone.is_manual = True
        self._num_of_zones[int(zone.zone_id)] = zone
        return zone

    def remove_discovered_zone(self, zone: str | LeaZone) -> None:
        """Remove Zone."""
        if isinstance(zone, LeaZone):
            zone = zone.zone_id
        if int(zone) in self._num_of_zones:
            del self._num_of_zones[int(zone)]

    def add_zone_to_queue(self, zone_id: int) -> bool:
        """Add Zone to queue."""
        if zone_id not in self._custom_zones_queue:
            self._custom_zones_queue.add(zone_id)
            return True
        return False

    def remove_zone_from_queue(self, zone_id: int) -> bool:
        """Remove zone from queue."""
        if zone_id in self._custom_zones_queue:
            self._custom_zones_queue.remove(zone_id)
            if zone := self.get_zone_by_zone_id(zone_id):
                if zone.is_manual:
                    self.remove_discovered_zone(zone)
            return True
        return False

    def cleanup(self) -> None:
        """Clean queue."""
        self._num_of_zones.clear()
        self._custom_zones_queue.clear()

    def get_zone_by_zone_id(self, zone_id: int) -> LeaZone | None:
        """Get zone by zone id."""
        return next(
            (
                zone
                for zone in self._num_of_zones.values()
                if int(zone.zone_id) == zone_id
            ),
            None,
        )

    @property
    def discovered_zones(self) -> dict[int, LeaZone]:
        """Return number of zones."""
        return self._num_of_zones

    @property
    def zones_queue(self) -> set[int]:
        """Return zones array."""
        return self._custom_zones_queue

    @property
    def has_queued_zones(self) -> bool:
        """Check if queue is full."""
        return bool(self._custom_zones_queue)
