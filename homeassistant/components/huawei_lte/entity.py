"""Support for Huawei LTE routers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import Router
from .const import UPDATE_SIGNAL

SCAN_INTERVAL = timedelta(seconds=10)


class HuaweiLteBaseEntity(Entity):
    """Huawei LTE entity base class."""

    _available = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, router: Router) -> None:
        """Initialize."""
        self.router = router
        self._unsub_handlers: list[Callable] = []

    @property
    def _device_unique_id(self) -> str:
        """Return unique ID for entity within a router."""
        raise NotImplementedError

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"{self.router.config_entry.unique_id}-{self._device_unique_id}"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update state."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Connect to update signals."""
        self._unsub_handlers.append(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._async_maybe_update)
        )

    async def _async_maybe_update(self, config_entry_unique_id: str) -> None:
        """Update state if the update signal comes from our router."""
        if config_entry_unique_id == self.router.config_entry.unique_id:
            self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Invoke unsubscription handlers."""
        for unsub in self._unsub_handlers:
            unsub()
        self._unsub_handlers.clear()


class HuaweiLteBaseEntityWithDevice(HuaweiLteBaseEntity):
    """Base entity with device info."""

    @property
    def device_info(self) -> DeviceInfo:
        """Get info for matching with parent router."""
        return DeviceInfo(
            connections=self.router.device_connections,
            identifiers=self.router.device_identifiers,
        )
