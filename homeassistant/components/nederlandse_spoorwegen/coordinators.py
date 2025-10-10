"""Coordinators manager for Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class NSCoordinatorsManager:
    """Manager for Nederlandse Spoorwegen coordinators."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinators manager."""
        self.hass = hass
        self.config_entry = config_entry
        self._coordinators: dict[str, NSDataUpdateCoordinator] = {}

    async def async_setup(self) -> None:
        """Set up coordinators for all existing routes."""
        for subentry_id, subentry in self.config_entry.subentries.items():
            if subentry.subentry_type == "route":
                await self.async_add_coordinator(subentry_id, subentry.data)

    async def async_reload_routes(self) -> None:
        """Reload routes, only updating what has changed."""
        current_routes = set(self._coordinators.keys())
        new_routes = {
            subentry_id
            for subentry_id, subentry in self.config_entry.subentries.items()
            if subentry.subentry_type == "route"
        }
        # Remove coordinators for routes that no longer exist
        stale_routes = current_routes - new_routes
        for route_id in stale_routes:
            await self.async_remove_coordinator(route_id)

        # Add coordinators for new routes
        untracked_routes = new_routes - current_routes
        for route_id in untracked_routes:
            subentry = self.config_entry.subentries[route_id]
            await self.async_add_coordinator(route_id, subentry.data)

        # For existing routes, we could check if data changed and update if needed
        # For now, keep them running as-is for efficiency

    async def async_add_coordinator(
        self, route_id: str, route_data: dict[str, Any] | Any
    ) -> NSDataUpdateCoordinator:
        """Add a new coordinator for a route."""
        if route_id in self._coordinators:
            _LOGGER.warning("Coordinator for route %s already exists", route_id)
            return self._coordinators[route_id]

        coordinator = NSDataUpdateCoordinator(
            self.hass, self.config_entry, route_id, route_data
        )

        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception as err:
            _LOGGER.error(
                "Failed to initialize coordinator for route %s: %s", route_id, err
            )
            raise

        self._coordinators[route_id] = coordinator
        _LOGGER.debug("Added coordinator for route %s", route_id)
        return coordinator

    async def async_remove_coordinator(self, route_id: str) -> None:
        """Remove a coordinator for a route."""
        if route_id not in self._coordinators:
            _LOGGER.warning("Coordinator for route %s does not exist", route_id)
            return

        self._coordinators.pop(route_id)
        _LOGGER.debug("Removed coordinator for route %s", route_id)

    def get_coordinator(self, route_id: str) -> NSDataUpdateCoordinator | None:
        """Get a coordinator for a specific route."""
        return self._coordinators.get(route_id)

    def get_all_coordinators(self) -> dict[str, NSDataUpdateCoordinator]:
        """Get all coordinators."""
        return self._coordinators.copy()

    def has_coordinator(self, route_id: str) -> bool:
        """Check if a coordinator exists for a route."""
        return route_id in self._coordinators

    async def async_refresh_all(self) -> None:
        """Refresh all coordinators."""
        for coordinator in self._coordinators.values():
            await coordinator.async_refresh()

    async def async_unload_all(self) -> None:
        """Unload all coordinators."""
        for route_id in list(self._coordinators.keys()):
            await self.async_remove_coordinator(route_id)

    @property
    def coordinator_count(self) -> int:
        """Return the number of active coordinators."""
        return len(self._coordinators)

    def get_route_ids(self) -> list[str]:
        """Get all route IDs that have coordinators."""
        return list(self._coordinators.keys())
