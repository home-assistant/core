"""Event platform for Kaleidescape."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from kaleidescape import const as kaleidescape_const

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
from homeassistant.const import CONF_COMMAND, CONF_PARAMS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaleidescapeConfigEntry
from .entity import KaleidescapeEntity

if TYPE_CHECKING:
    from kaleidescape import Device as KaleidescapeDevice

_LOGGER = logging.getLogger(__name__)

# Event type constants
EVENT_VOLUME_QUERY = "volume_query"
EVENT_VOLUME_SET = "volume_set"
EVENT_VOLUME_UP = "volume_up"
EVENT_VOLUME_DOWN = "volume_down"
EVENT_VOLUME_MUTE = "volume_mute"
EVENT_USER_DEFINED = "user_defined"

TRIGGERED = "triggered"
DEBOUNCE_TIME = 0.5

KALEIDESCAPE_EVENTS_VOLUME_UP = (
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_UP,
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_UP_PRESS,
)

KALEIDESCAPE_EVENTS_VOLUME_DOWN = (
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_DOWN,
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_DOWN_PRESS,
)


@dataclass(kw_only=True, frozen=True)
class KaleidescapeEventEntityDescription(EventEntityDescription):
    """Describes Kaleidescape event entity."""

    device_user_event_names: tuple[str, ...]
    event_handle_fn: Callable[[KaleidescapeEventEntity, str, list[str]], None] = (
        lambda e, c, f: e.handle_user_defined_volume_event(c, f)
    )


EVENT_DESCRIPTIONS = [
    KaleidescapeEventEntityDescription(
        key=EVENT_VOLUME_QUERY,
        translation_key=EVENT_VOLUME_QUERY,
        event_types=[TRIGGERED],
        device_user_event_names=(kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY,),
    ),
    KaleidescapeEventEntityDescription(
        key=EVENT_VOLUME_SET,
        translation_key=EVENT_VOLUME_SET,
        event_types=[TRIGGERED],
        event_handle_fn=lambda e, c, f: e.handle_user_defined_volume_set_event(c, f),
        device_user_event_names=(
            kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL,
        ),
    ),
    KaleidescapeEventEntityDescription(
        key=EVENT_VOLUME_UP,
        translation_key=EVENT_VOLUME_UP,
        event_types=[TRIGGERED],
        device_user_event_names=KALEIDESCAPE_EVENTS_VOLUME_UP,
    ),
    KaleidescapeEventEntityDescription(
        key=EVENT_VOLUME_DOWN,
        translation_key=EVENT_VOLUME_DOWN,
        event_types=[TRIGGERED],
        device_user_event_names=KALEIDESCAPE_EVENTS_VOLUME_DOWN,
    ),
    KaleidescapeEventEntityDescription(
        key=EVENT_VOLUME_MUTE,
        translation_key=EVENT_VOLUME_MUTE,
        event_types=[TRIGGERED],
        device_user_event_names=(kaleidescape_const.USER_DEFINED_EVENT_TOGGLE_MUTE,),
    ),
    KaleidescapeEventEntityDescription(
        key=EVENT_USER_DEFINED,
        translation_key=EVENT_USER_DEFINED,
        event_types=[TRIGGERED],
        event_handle_fn=lambda e, c, f: e.handle_user_defined_event(c, f),
        device_user_event_names=(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KaleidescapeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    async_add_entities(
        [
            KaleidescapeEventEntity(entry.runtime_data, description)
            for description in EVENT_DESCRIPTIONS
        ]
    )


class KaleidescapeEventEntity(KaleidescapeEntity, EventEntity):
    """Representation of a Kaleidescape event."""

    entity_description: KaleidescapeEventEntityDescription

    def __init__(
        self,
        device: KaleidescapeDevice,
        entity_description: KaleidescapeEventEntityDescription,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(device)
        self.entity_description: KaleidescapeEventEntityDescription = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"
        self._debounce: asyncio.TimerHandle | None = None

    async def _async_handle_event(self, event: str, *args: Any) -> None:
        """Handle device events."""
        if event != kaleidescape_const.USER_DEFINED_EVENT:
            return

        if not args or not isinstance(args[0], list) or not args[0]:
            return

        command, params = args[0][0], args[0][1:]

        if (
            command in self.entity_description.device_user_event_names
            or self.entity_description.key == EVENT_USER_DEFINED
        ):
            self.entity_description.event_handle_fn(self, command, params)

    @callback
    def handle_user_defined_volume_event(self, command: str, params: list[str]) -> None:
        """Handle volume related device events."""
        _LOGGER.debug("Received USER_DEFINED_EVENT: %s %s", command, params)

        self._trigger_event(TRIGGERED)

        self.async_write_ha_state()

    @callback
    def handle_user_defined_volume_set_event(
        self, command: str, params: list[str]
    ) -> None:
        """Handle volume set device events."""
        _LOGGER.debug("Received USER_DEFINED_EVENT: %s %s", command, params)

        try:
            volume_level = int(params[0])
        except (IndexError, ValueError, TypeError):
            _LOGGER.warning("Invalid level for SET_VOLUME_LEVEL: %s", params)
            return

        scaled_volume_level = float(max(0, min(100, volume_level)) / 100)

        if self._debounce is not None:
            self._debounce.cancel()
            self._debounce = None

        def _trigger() -> None:
            self._debounce = None
            self._trigger_event(
                TRIGGERED, {ATTR_MEDIA_VOLUME_LEVEL: scaled_volume_level}
            )
            self.async_write_ha_state()

        self._debounce = self.hass.loop.call_later(DEBOUNCE_TIME, _trigger)

    @callback
    def handle_user_defined_event(self, command: str, params: list[str]) -> None:
        """Handle custom user defined device events."""
        if command in kaleidescape_const.VOLUME_EVENTS:
            # Ignore all volume related events
            return

        _LOGGER.debug("Received USER_DEFINED_EVENT: %s %s", command, params)

        self._trigger_event(TRIGGERED, {CONF_COMMAND: command, CONF_PARAMS: params})

        self.async_write_ha_state()
