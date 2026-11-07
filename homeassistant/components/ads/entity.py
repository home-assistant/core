"""Support for Automation Device Specification (ADS)."""

import asyncio
from asyncio import timeout
import logging
from typing import Any, override

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform

from .const import STATE_KEY_STATE
from .hub import AdsHub

_LOGGER = logging.getLogger(__name__)


class AdsEntity(Entity):
    """Representation of ADS entity."""

    _attr_should_poll = False

    def __init__(self, ads_hub: AdsHub, name: str, ads_var: str) -> None:
        """Initialize ADS binary sensor."""
        self._state_dict: dict[str, Any] = {}
        self._state_dict[STATE_KEY_STATE] = None
        self._ads_hub = ads_hub
        self._ads_var = ads_var
        self._notification_handles: list[int] = []
        self._first_updates: list[asyncio.Event] = []
        self._removed = False
        self._attr_unique_id = ads_var
        self._attr_name = name

    @callback
    @override
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform.

        The same instance is added again after an entity ID change, so the
        removal preceding it must not disarm the new subscriptions.
        """
        super().add_to_platform_start(hass, platform, parallel_updates)
        self._removed = False

    async def async_initialize_device(
        self,
        ads_var: str,
        plctype: type,
        state_key: str = STATE_KEY_STATE,
        factor: int | None = None,
    ) -> None:
        """Register device notification."""

        def update(name, value):
            """Handle device notifications."""
            _LOGGER.debug("Variable %s changed its value to %d", name, value)

            if factor is None:
                self._state_dict[state_key] = value
            else:
                self._state_dict[state_key] = value / factor

            # Callbacks arrive on a pyads thread, so hop to the event loop.
            self.hass.loop.call_soon_threadsafe(event.set)
            self.schedule_update_ha_state()

        event = asyncio.Event()

        handle = await self.hass.async_add_executor_job(
            self._ads_hub.add_device_notification, ads_var, plctype, update
        )
        if handle is None:
            return
        if self._removed:
            # Removed while this was subscribing, so the removal has already
            # drained the handles and will not come back for this one.
            await self.hass.async_add_executor_job(
                self._ads_hub.delete_device_notification, handle
            )
            return
        self._notification_handles.append(handle)
        self._first_updates.append(event)
        try:
            async with timeout(10):
                await event.wait()
        except TimeoutError:
            _LOGGER.debug("Variable %s: Timeout during first update", ads_var)
        finally:
            self._first_updates.remove(event)

    @property
    @override
    def available(self) -> bool:
        """Return False if state has not been updated yet."""
        return self._state_dict[STATE_KEY_STATE] is not None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Drop the subscriptions this entity added.

        The hub holds the callback, so leaving them behind would keep the PLC
        pushing values for a variable nobody reads and pin this entity.
        """
        # Set before the first await, so a subscription still in flight sees it
        # and cleans up after itself.
        self._removed = True
        # Nothing will deliver a first update any more, so stop waiting for one.
        for event in self._first_updates:
            event.set()
        handles = self._notification_handles
        self._notification_handles = []
        for handle in handles:
            await self.hass.async_add_executor_job(
                self._ads_hub.delete_device_notification, handle
            )
