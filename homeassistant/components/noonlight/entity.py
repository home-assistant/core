"""Shared base entity for the Noonlight integration.

Not in the spec's illustrative layout, but a standard HA pattern: it keeps the
device grouping and ``has_entity_name`` wiring in one place instead of being
duplicated across ``binary_sensor.py`` and ``sensor.py``.
"""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NoonlightCoordinator


class NoonlightEntity(CoordinatorEntity[NoonlightCoordinator]):
    """Base entity tying every Noonlight entity to its config-entry device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NoonlightCoordinator, key: str) -> None:
        """Initialise with a stable per-entry ``key`` (e.g. ``dispatch_state``)."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            # Naming the device "Noonlight <account>" yields entity ids like
            # ``binary_sensor.noonlight_<account>_dispatch_pending``.
            name=f"Noonlight {coordinator.entry.title}",
            manufacturer="Noonlight",
            model="Dispatch",
        )
