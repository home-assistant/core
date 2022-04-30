"""Module for SIA Base Entity."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
import logging

from pysiaalarm import SIAEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .const import (
    AVAILABILITY_EVENT_CODE,
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    DOMAIN,
    SIA_EVENT,
    SIA_HUB_ZONE,
)
from .utils import (
    get_attr_from_sia_event,
    get_unavailability_interval,
    get_unique_id_and_name,
)

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
        entry: ConfigEntry,
        account: str,
        zone: int,
        entity_description: SIAEntityDescription,
    ) -> None:
        """Create SIABaseEntity object."""
        self.port = entry.data[CONF_PORT]
        self.account = account
        self.zone = zone
        self.entity_description = entity_description

        self.ping_interval: int = next(
            acc[CONF_PING_INTERVAL]
            for acc in entry.data[CONF_ACCOUNTS]
            if acc[CONF_ACCOUNT] == account
        )
        self._attr_unique_id, self._attr_name = get_unique_id_and_name(
            entry.entry_id, entry.data[CONF_PORT], account, zone, entity_description.key
        )
        self._attr_device_info = DeviceInfo(
            name=self._attr_name,
            identifiers={(DOMAIN, self._attr_unique_id)},
            via_device=(DOMAIN, f"{entry.data[CONF_PORT]}_{account}"),
        )

        self._post_interval_update_cb_canceller: CALLBACK_TYPE | None = None
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
            self.async_create_post_interval_update_cb()

    @abstractmethod
    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        Overridden from Entity.
        """
        self._cancel_post_interval_update_cb()

    @callback
    def async_handle_event(self, sia_event: SIAEvent) -> None:
        """Listen to dispatcher events for this port and account and update state and attributes.

        If the event is for either the zone or the 0 zone (hub zone), then handle it further.
        If the event had a code that was relevant for the entity, then update the attributes.
        If the event had a code that was relevant or it was a availability event then update the availability and schedule the next unavailability check.
        """
        _LOGGER.debug("Received event: %s", sia_event)
        if int(sia_event.ri) not in (self.zone, SIA_HUB_ZONE):
            return

        relevant_event = self.update_state(sia_event)

        if relevant_event:
            self._attr_extra_state_attributes.update(get_attr_from_sia_event(sia_event))

        if relevant_event or sia_event.code == AVAILABILITY_EVENT_CODE:
            self._attr_available = True
            self._cancel_post_interval_update_cb()
            self.async_create_post_interval_update_cb()

        self.async_write_ha_state()

    @abstractmethod
    def update_state(self, sia_event: SIAEvent) -> bool:
        """Do the entity specific state updates.

        Return True if the event was relevant for this entity.
        """

    @callback
    def async_create_post_interval_update_cb(self) -> None:
        """Create a port interval update cb and store the callback."""
        self._post_interval_update_cb_canceller = async_call_later(
            self.hass,
            get_unavailability_interval(self.ping_interval),
            self.async_post_interval_update,
        )

    @callback
    def async_post_interval_update(self, _) -> None:
        """Set unavailable after a ping interval."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def _cancel_post_interval_update_cb(self) -> None:
        """Cancel the callback."""
        if self._post_interval_update_cb_canceller:
            self._post_interval_update_cb_canceller()
            self._post_interval_update_cb_canceller = None
