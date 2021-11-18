"""Module for SIA Base Entity."""
from __future__ import annotations

from abc import abstractmethod
import logging

from pysiaalarm import SIAEvent

from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SIA_EVENT, SIA_HUB_ZONE
from .utils import (
    SIAAlarmControlPanelEntityDescription,
    SIABinarySensorEntityDescription,
    get_attr_from_sia_event,
    get_unavailability_interval,
)

_LOGGER = logging.getLogger(__name__)


class SIABaseEntity(RestoreEntity):
    """Base class for SIA entities."""

    entity_description: SIAAlarmControlPanelEntityDescription | SIABinarySensorEntityDescription

    def __init__(
        self,
        entity_description: SIAAlarmControlPanelEntityDescription
        | SIABinarySensorEntityDescription,
    ) -> None:
        """Create SIABaseEntity object."""
        self.entity_description = entity_description
        self._cancel_availability_cb: CALLBACK_TYPE | None = None
        self._attr_extra_state_attributes = {}
        self._attr_should_poll = False

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
                SIA_EVENT.format(
                    self.entity_description.port, self.entity_description.account
                ),
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

        If the zone matches or the message is for the hub zone (0) it means the entity is online and can therefore be set to available.
        """
        _LOGGER.debug("Received event: %s", sia_event)
        if int(sia_event.ri) not in (self.entity_description.zone, SIA_HUB_ZONE):
            return
        self._attr_extra_state_attributes.update(get_attr_from_sia_event(sia_event))
        state_changed = self.update_state(sia_event)
        if state_changed or self.entity_description.always_reset_availability:
            self.async_reset_availability_cb()
        self.async_write_ha_state()

    @abstractmethod
    def update_state(self, sia_event: SIAEvent) -> bool:
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
            get_unavailability_interval(self.entity_description.ping_interval),
            self.async_set_unavailable,
        )

    @callback
    def async_set_unavailable(self, _) -> None:
        """Set unavailable."""
        self._attr_available = False
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.entity_description.key

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info."""
        return DeviceInfo(
            name=self.name,
            identifiers={(DOMAIN, self.unique_id)},
            via_device=(
                DOMAIN,
                f"{self.entity_description.port}_{self.entity_description.account}",
            ),
        )
