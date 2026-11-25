"""Support for Automation Device Specification (ADS)."""

import asyncio
from asyncio import timeout
from collections.abc import Callable
import logging
from typing import Any, override

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

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
        self._subscription_ids: list[int] = []
        self._removed = False
        self._subscribe_task: asyncio.Task[None] | None = None
        self._attr_unique_id = ads_var
        self._attr_name = name
        ads_hub.register_device(self)
        # Also runs when the entity platform refuses to add this entity, so a
        # rejected one is not left behind on the hub.
        self.async_on_remove(self._unregister_from_hub)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe once the entity is added."""
        await self.async_run_subscribe()

    async def async_run_subscribe(self) -> None:
        """Run async_subscribe in a task that a rebind to a new hub cancels.

        Otherwise a subscription still waiting for a first value would carry on
        against the new hub next to its replacement and subscribe twice.
        """
        self._subscribe_task = task = self.hass.async_create_task(
            self.async_subscribe(), f"ads subscribe {self._ads_var}"
        )
        try:
            await task
        except asyncio.CancelledError:
            # Only swallow the cancellation of the subscription itself.
            if (current := asyncio.current_task()) and current.cancelling():
                raise

    async def async_subscribe(self) -> None:
        """Subscribe to the PLC variables of this entity.

        Also called after the entry is reloaded, to subscribe again on the new
        hub.
        """
        raise NotImplementedError

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

        if not await self.async_add_notification(ads_var, plctype, update):
            return
        try:
            async with timeout(10):
                await event.wait()
        except TimeoutError:
            _LOGGER.debug("Variable %s: Timeout during first update", ads_var)

    async def async_add_notification(
        self,
        ads_var: str,
        plctype: type,
        notification_callback: Callable[[str, Any], None],
    ) -> bool:
        """Subscribe to a variable, returning whether the device notifies on it.

        The subscription is tracked, so removing the entity deletes it again.
        One the device refused is kept on the hub and asked for again on the
        next reconnect.
        """
        subscription_id = await self.hass.async_add_executor_job(
            self._ads_hub.add_device_notification,
            ads_var,
            plctype,
            notification_callback,
        )
        if subscription_id is None:
            # No notification is registered, so no first update will arrive.
            return False
        if self._removed:
            # Removed while this was subscribing, so the removal has already
            # drained the subscriptions and will not come back for this one.
            await self.hass.async_add_executor_job(
                self._ads_hub.delete_device_notification, subscription_id
            )
            return False
        self._subscription_ids.append(subscription_id)
        return await self.hass.async_add_executor_job(
            self._ads_hub.is_registered, subscription_id
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the PLC runs and has sent a value.

        Values that arrive while the PLC is stopped are kept, so the latest one
        shows as soon as it runs again.
        """
        return self._ads_hub.connected and self._state_dict[STATE_KEY_STATE] is not None

    @callback
    def async_connection_changed(self) -> None:
        """Update the state after the hub's connection came or went."""
        if self.hass is not None and self.platform is not None:
            self.async_write_ha_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Drop the subscriptions this entity added.

        The hub holds the callback, so leaving them behind would keep the PLC
        pushing values for a variable nobody reads and pin this entity.
        """
        # Set before the first await, so a subscription still in flight sees it
        # and cleans up after itself.
        self._removed = True
        subscription_ids = self._subscription_ids
        self._subscription_ids = []
        for subscription_id in subscription_ids:
            await self.hass.async_add_executor_job(
                self._ads_hub.delete_device_notification, subscription_id
            )

    def mark_unavailable(self) -> None:
        """Mark the entity unavailable after its hub connection is closed."""
        # Notification callbacks add keys from another thread, so snapshot them.
        for key in list(self._state_dict):
            self._state_dict[key] = None
        if self.hass is not None:
            self.schedule_update_ha_state()

    @callback
    def _unregister_from_hub(self) -> None:
        """Unregister this entity from its hub."""
        self._ads_hub.unregister_device(self)

    def rebind(self, ads_hub: AdsHub) -> None:
        """Rebind this entity to a new hub after the entry is reloaded."""
        if self._subscribe_task is not None:
            self._subscribe_task.cancel()
            self._subscribe_task = None
        self._ads_hub = ads_hub
        # The old hub's subscriptions died with it, and the new one hands out
        # the same ids again.
        self._subscription_ids.clear()
        ads_hub.register_device(self)
