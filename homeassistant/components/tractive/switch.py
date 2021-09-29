"""Support for Tractive switches."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiotractive.exceptions import TractiveError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_BUZZER,
    ATTR_LED,
    ATTR_LIVE_TRACKING,
    CLIENT,
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKABLES,
    TRACKER_HARDWARE_STATUS_UPDATED,
)
from .entity import TractiveEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class TractiveSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Tractive switch entities."""

    method: str | None = None


SWITCH_TYPES = (
    TractiveSwitchEntityDescription(
        key=ATTR_BUZZER,
        name="Tracker Buzzer",
        icon="mdi:volume-high",
        method="async_set_buzzer",
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LED,
        name="Tracker LED",
        icon="mdi:led-on",
        method="async_set_led",
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LIVE_TRACKING,
        name="Live Tracking",
        icon="mdi:map-marker-path",
        method="async_set_live_tracking",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive switches."""
    client = hass.data[DOMAIN][entry.entry_id][CLIENT]
    trackables = hass.data[DOMAIN][entry.entry_id][TRACKABLES]

    entities = []

    for trackable in trackables:
        for description in SWITCH_TYPES:
            entities.append(
                TractiveSwitch(
                    client.user_id,
                    trackable,
                    description,
                )
            )

    async_add_entities(entities)


class TractiveSwitch(TractiveEntity, SwitchEntity):
    """Tractive switch."""

    entity_description: TractiveSwitchEntityDescription

    def __init__(self, user_id, trackable, description):
        """Initialize switch entity."""
        super().__init__(user_id, trackable.trackable, trackable.tracker_details)

        self._attr_name = f"{trackable.trackable['details']['name']} {description.name}"
        self._attr_unique_id = f"{trackable.trackable['_id']}_{description.key}"
        self._attr_available = False
        self._tracker = trackable.tracker
        self._method = getattr(self, description.method)
        self.entity_description = description

    @callback
    def handle_server_unavailable(self):
        """Handle server unavailable."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def handle_hardware_status_update(self, event):
        """Handle hardware status update."""
        if (_state := event[self.entity_description.key]) is None:
            return
        self._attr_is_on = _state
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_HARDWARE_STATUS_UPDATED}-{self._tracker_id}",
                self.handle_hardware_status_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._user_id}",
                self.handle_server_unavailable,
            )
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on a switch."""
        try:
            result = await self._method(True)
        except TractiveError as error:
            _LOGGER.error(error)
            return
        # Write state back to avoid switch flips with a slow response
        if result["pending"]:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off a switch."""
        try:
            result = await self._method(False)
        except TractiveError as error:
            _LOGGER.error(error)
            return
        # Write state back to avoid switch flips with a slow response
        if result["pending"]:
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_set_buzzer(self, active: bool) -> dict[str, Any]:
        """Set the buzzer on/off."""
        return await self._tracker.set_buzzer_active(active)

    async def async_set_led(self, active: bool) -> dict[str, Any]:
        """Set the LED on/off."""
        return await self._tracker.set_led_active(active)

    async def async_set_live_tracking(self, active: bool) -> dict[str, Any]:
        """Set the live tracking on/off."""
        return await self._tracker.set_live_tracking_active(active)
