"""Tracks devices by sending a ICMP echo request (ping)."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    ScannerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import PingConfigEntry
from .const import CONF_IMPORTED_BY
from .coordinator import PingUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: PingConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Ping config entry."""
    async_add_entities([PingDeviceTracker(entry, entry.runtime_data)])


class PingDeviceTracker(CoordinatorEntity[PingUpdateCoordinator], ScannerEntity):
    """Representation of a Ping device tracker."""

    _last_seen: datetime | None = None

    def __init__(
        self, config_entry: ConfigEntry, coordinator: PingUpdateCoordinator
    ) -> None:
        """Initialize the Ping device tracker."""
        super().__init__(coordinator)

        self._attr_name = config_entry.title
        self.config_entry = config_entry
        self._consider_home_interval = timedelta(
            seconds=config_entry.options.get(
                CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.seconds
            )
        )

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.coordinator.data.ip_address

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.config_entry.entry_id

    @property
    def is_connected(self) -> bool:
        """Return true if ping returns is_alive or considered home."""
        if self.coordinator.data.is_alive:
            self._last_seen = dt_util.utcnow()

        return (
            self._last_seen is not None
            and (dt_util.utcnow() - self._last_seen) < self._consider_home_interval
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        if CONF_IMPORTED_BY in self.config_entry.data:
            return bool(self.config_entry.data[CONF_IMPORTED_BY] == "device_tracker")
        return False
