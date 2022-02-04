"""Module for SIA Base Entity."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
import logging

from pysiaalarm import SIAEvent

from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .const import AVAILABILITY_EVENT_CODE, DOMAIN, SIA_EVENT, SIA_HUB_ZONE
from .utils import get_attr_from_sia_event, get_unavailability_interval

_LOGGER = logging.getLogger(__name__)


@dataclass
class SIARequiredKeysMixin:
    """Required keys for SIA entities."""

    code_consequences: dict[str, StateType | bool]


@dataclass
class SIAEntityDescription(EntityDescription, SIARequiredKeysMixin):
    """Entity Description for SIA entities."""


class SIABaseEntity(RestoreEntity):
    """Base class for SIA entities."""

    entity_description: SIAEntityDescription

    def __init__(
        self,
        port: int,
        account: str,
        zone: int | None,
        ping_interval: int,
        entity_description: SIAEntityDescription,
        unique_id: str,
        name: str,
    ) -> None:
        """Create SIABaseEntity object."""
        self.port = port
        self.account = account
        self.zone = zone
        self.ping_interval = ping_interval
        self.entity_description = entity_description
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            name=name,
            identifiers={(DOMAIN, unique_id)},
            via_device=(DOMAIN, f"{port}_{account}"),
        )

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
                SIA_EVENT.format(self.port, self.account),
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
        """Listen to dispatcher events for this port and account and update state and attributes."""
        _LOGGER.debug("Received event: %s", sia_event)
        if int(sia_event.ri) not in (self.zone, SIA_HUB_ZONE):
            return
        self._attr_extra_state_attributes.update(get_attr_from_sia_event(sia_event))
        state_changed = self.update_state(sia_event)
        if state_changed or sia_event.code == AVAILABILITY_EVENT_CODE:
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
            get_unavailability_interval(self.ping_interval),
            self.async_set_unavailable,
        )

    @callback
    def async_set_unavailable(self, _) -> None:
        """Set unavailable."""
        self._attr_available = False
        self.async_write_ha_state()
