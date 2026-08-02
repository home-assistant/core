"""Tracks devices by sending a ICMP echo request (ping)."""

from datetime import datetime, timedelta
from typing import override

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    BaseScannerEntity,
    SourceType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_IMPORTED_BY
from .coordinator import PingConfigEntry, PingUpdateCoordinator
from .entity import PingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Ping config entry."""
    async_add_entities([PingDeviceTracker(entry, entry.runtime_data)])


class PingDeviceTracker(PingEntity, BaseScannerEntity):
    """Representation of a Ping device tracker."""

    _attr_name = None
    _attr_source_type = SourceType.ROUTER
    _last_seen: datetime | None = None

    def __init__(
        self,
        config_entry: PingConfigEntry,
        coordinator: PingUpdateCoordinator,
    ) -> None:
        """Initialize the Ping device tracker."""
        super().__init__(config_entry, coordinator, config_entry.entry_id)

        self.config_entry = config_entry
        self._consider_home_interval = timedelta(
            seconds=config_entry.options.get(
                CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.seconds
            )
        )

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if ping returns is_alive or considered home."""
        if self.coordinator.data.is_alive:
            self._last_seen = dt_util.utcnow()

        return (
            self._last_seen is not None
            and (dt_util.utcnow() - self._last_seen) < self._consider_home_interval
        )

    @property
    @override
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        if CONF_IMPORTED_BY in self.config_entry.data:
            return bool(self.config_entry.data[CONF_IMPORTED_BY] == "device_tracker")
        return False
