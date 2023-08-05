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

from . import Trackables, TractiveClient
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
        translation_key="tracker_buzzer",
        icon="mdi:volume-high",
        method="async_set_buzzer",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LED,
        translation_key="tracker_led",
        icon="mdi:led-on",
        method="async_set_led",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LIVE_TRACKING,
        translation_key="live_tracking",
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
        TractiveSwitch(client, item, description)
        for description in SWITCH_TYPES
        for item in trackables
    ]

    async_add_entities(entities)


class TractiveSwitch(TractiveEntity, SwitchEntity):
    """Tractive switch."""

    entity_description: TractiveSwitchEntityDescription

    def __init__(
        self,
        client: TractiveClient,
        item: Trackables,
        description: TractiveSwitchEntityDescription,
    ) -> None:
        """Initialize switch entity."""
        super().__init__(client, item.trackable, item.tracker_details)

        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self._attr_available = False
        self._tracker = item.tracker
        self._method = getattr(self, description.method)
        self.entity_description = description

    @callback
    def handle_status_update(self, event: dict[str, Any]) -> None:
        """Handle status update."""
        self._attr_is_on = event[self.entity_description.key]

        super().handle_status_update(event)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_HARDWARE_STATUS_UPDATED}-{self._tracker_id}",
                self.handle_status_update,
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
