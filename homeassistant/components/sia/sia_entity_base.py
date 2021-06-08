"""Module for SIA Base Entity."""
from __future__ import annotations

from abc import abstractmethod
import logging
from typing import Any

from pysiaalarm import SIAEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_ACCOUNT, CONF_PING_INTERVAL, DOMAIN, SIA_EVENT, SIA_NAME_FORMAT
from .utils import get_attr_from_sia_event, get_unavailability_interval

_LOGGER = logging.getLogger(__name__)


class SIABaseEntity(RestoreEntity):
    """Base class for SIA entities."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
        zone: int,
        device_class: str,
    ) -> None:
        """Create SIABaseEntity object."""
        self._entry: ConfigEntry = entry
        self._account_data: dict[str, Any] = account_data
        self._zone: int = zone
        self._attr_device_class: str = device_class

        self._port: int = self._entry.data[CONF_PORT]
        self._account: str = self._account_data[CONF_ACCOUNT]
        self._ping_interval: int = self._account_data[CONF_PING_INTERVAL]

        self._cancel_availability_cb: CALLBACK_TYPE | None = None

        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._attr_should_poll = False
        self._attr_name = SIA_NAME_FORMAT.format(
            self._port, self._account, self._zone, self._attr_device_class
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        Overridden from Entity.

        1. register the dispatcher and add the callback to on_remove
        2. get previous state from storage and pass to entity specific function
        3. if available: create availability cb
        """
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIA_EVENT.format(self._port, self._account),
                self.async_handle_event,
            )
        )
        self.handle_last_state(await self.async_get_last_state())
        if self._attr_available:
            self.async_create_availability_cb()

    @abstractmethod
    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        Overridden from Entity.
        """
        if self._cancel_availability_cb:
            self._cancel_availability_cb()

    @callback
    def async_handle_event(self, sia_event: SIAEvent) -> None:
        """Listen to dispatcher events for this port and account and update state and attributes.

        If the port and account combo receives any message it means it is online and can therefore be set to available.
        """
        _LOGGER.debug("Received event: %s", sia_event)
        if int(sia_event.ri) == self._zone:
            self._attr_extra_state_attributes.update(get_attr_from_sia_event(sia_event))
            self.update_state(sia_event)
        self.async_reset_availability_cb()
        self.async_write_ha_state()

    @abstractmethod
    def update_state(self, sia_event: SIAEvent) -> None:
        """Do the entity specific state updates."""

    @callback
    def async_reset_availability_cb(self) -> None:
        """Reset availability cb by cancelling the current and creating a new one."""
        self._attr_available = True
        if self._cancel_availability_cb:
            self._cancel_availability_cb()
        self.async_create_availability_cb()

    def async_create_availability_cb(self) -> None:
        """Create a availability cb and return the callback."""
        self._cancel_availability_cb = async_call_later(
            self.hass,
            get_unavailability_interval(self._ping_interval),
            self.async_set_unavailable,
        )

    @callback
    def async_set_unavailable(self, _) -> None:
        """Set unavailable."""
        self._attr_available = False
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info."""
        assert self._attr_name is not None
        assert self.unique_id is not None
        return {
            "name": self._attr_name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "via_device": (DOMAIN, f"{self._port}_{self._account}"),
        }
