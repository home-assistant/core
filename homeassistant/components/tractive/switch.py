"""Support for Tractive switches."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Literal, cast

from aiotractive.exceptions import TractiveError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Trackables, TractiveClient, TractiveConfigEntry
from .const import (
    ATTR_BUZZER,
    ATTR_LED,
    ATTR_LIVE_TRACKING,
    TRACKER_SWITCH_STATUS_UPDATED,
)
from .entity import TractiveEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TractiveSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Tractive switch entities."""

    method: Literal["async_set_buzzer", "async_set_led", "async_set_live_tracking"]


SWITCH_TYPES: tuple[TractiveSwitchEntityDescription, ...] = (
    TractiveSwitchEntityDescription(
        key=ATTR_BUZZER,
        translation_key="tracker_buzzer",
        method="async_set_buzzer",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LED,
        translation_key="tracker_led",
        method="async_set_led",
        entity_category=EntityCategory.CONFIG,
    ),
    TractiveSwitchEntityDescription(
        key=ATTR_LIVE_TRACKING,
        translation_key="live_tracking",
        method="async_set_live_tracking",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tractive switches."""
    client = entry.runtime_data.client
    trackables = entry.runtime_data.trackables

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
        super().__init__(
            client,
            item.trackable,
            item.tracker_details,
            f"{TRACKER_SWITCH_STATUS_UPDATED}-{item.tracker_details['_id']}",
        )

        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self._tracker = item.tracker
        self._method = getattr(self, description.method)
        self.entity_description = description

    @callback
    def handle_status_update(self, event: dict[str, Any]) -> None:
        """Handle status update."""
        if self.entity_description.key not in event:
            return

        # We received an event, so the service is online and the switch entities should
        #  be available.
        self._attr_available = True
        self._attr_is_on = event[self.entity_description.key]

        self.async_write_ha_state()

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
