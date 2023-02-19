"""Support for Tractive switches."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Literal, cast

from aiotractive.exceptions import TractiveError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Trackables
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
class TractiveRequiredKeysMixin:
    """Mixin for required keys."""

    method: Literal["async_set_buzzer", "async_set_led", "async_set_live_tracking"]


@dataclass
class TractiveSwitchEntityDescription(
    SwitchEntityDescription, TractiveRequiredKeysMixin
):
    """Class describing Tractive switch entities."""


SWITCH_TYPES: tuple[TractiveSwitchEntityDescription, ...] = (
    TractiveSwitchEntityDescription(
        key=ATTR_BUZZER,
        name="Tracker buzzer",
        icon="mdi:volume-high",
        method="async_set_buzzer",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LED,
        name="Tracker LED",
        icon="mdi:led-on",
        method="async_set_led",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LIVE_TRACKING,
        name="Live tracking",
        icon="mdi:map-marker-path",
        method="async_set_live_tracking",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tractive switches."""
    client = hass.data[DOMAIN][entry.entry_id][CLIENT]
    trackables = hass.data[DOMAIN][entry.entry_id][TRACKABLES]

    entities = [
        TractiveSwitch(client.user_id, item, description)
        for description in SWITCH_TYPES
        for item in trackables
    ]

    async_add_entities(entities)


class TractiveSwitch(TractiveEntity, SwitchEntity):
    """Tractive switch."""

    _attr_has_entity_name = True
    entity_description: TractiveSwitchEntityDescription

    def __init__(
        self,
        user_id: str,
        item: Trackables,
        description: TractiveSwitchEntityDescription,
    ) -> None:
        """Initialize switch entity."""
        super().__init__(user_id, item.trackable, item.tracker_details)

        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self._attr_available = False
        self._tracker = item.tracker
        self._method = getattr(self, description.method)
        self.entity_description = description

    @callback
    def handle_server_unavailable(self) -> None:
        """Handle server unavailable."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def handle_hardware_status_update(self, event: dict[str, Any]) -> None:
        """Handle hardware status update."""
        if (state := event[self.entity_description.key]) is None:
            return
        self._attr_is_on = state
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
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

    async def async_turn_on(self, **kwargs: Any) -> None:
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

    async def async_turn_off(self, **kwargs: Any) -> None:
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
        return cast(dict[str, Any], await self._tracker.set_buzzer_active(active))

    async def async_set_led(self, active: bool) -> dict[str, Any]:
        """Set the LED on/off."""
        return cast(dict[str, Any], await self._tracker.set_led_active(active))

    async def async_set_live_tracking(self, active: bool) -> dict[str, Any]:
        """Set the live tracking on/off."""
        return cast(
            dict[str, Any], await self._tracker.set_live_tracking_active(active)
        )
