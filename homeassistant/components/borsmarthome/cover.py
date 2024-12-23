"""Ave tapparella."""

import asyncio
import asyncio.coroutines
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import HubConfigEntry
from .hub import AveHub, RollerShutter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cover for passed config_entry in HA."""
    # The hub is loaded from the associated entry runtime data that was set in the
    # __init__.async_setup_entry function
    hub = config_entry.runtime_data

    # Add all entities to HA
    async_add_entities(TapparellaEntity(roller, hub) for roller in hub.devices)


class TapparellaEntity(CoverEntity):
    """Ave shutter entity in ha."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.SHUTTER
    unsub = None
    task: asyncio.Task = None

    def __init__(self, roller: RollerShutter, hub: AveHub) -> None:
        """Initialize the entity."""
        self._name = roller.name
        self._roller = roller
        self._channel = roller.name
        self._hub = hub
        self._set_current_position(roller.position)
        self.unique_id = f"avebus_{roller.name}"
        self._loop = asyncio.get_event_loop()

    @property
    def name(self) -> str:
        """Friendly name."""
        return self._name

    @property
    def channel(self):
        """Ave channel."""
        return self._channel

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Get supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    def _set_current_position(self, position: int):
        """Set position."""
        self.is_closed = position < 1
        self.current_cover_position = position

    async def _async_on_change(self, event: Event[EventStateChangedData]) -> None:
        """On change callback."""
        new_state = event.data.get("new_state")
        external = new_state.context.user_id is not None

        _LOGGER.debug("State: %s External: %s", new_state, external)

        state = new_state.state.lower()
        if state == "closing":
            self.is_closing = True
        elif state == "opening":
            self.is_opening = True
        else:
            self.is_opening = False
            self.is_closing = False
            current_position = new_state.attributes.get("current_position")
            if current_position is not None:
                self._set_current_position(current_position)

        await self._roller.async_publish_updates()

    async def async_will_remove_from_hass(self) -> None:
        """On remove from hass."""
        self.unsub()
        self._roller.remove_callback(self.async_write_ha_state)

    async def async_added_to_hass(self) -> None:
        """On add to hass."""
        self.unsub = async_track_state_change_event(
            self.hass, self.entity_id, self._async_on_change
        )
        self._roller.register_callback(self.async_write_ha_state)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Apri la tapparella."""
        await self._roller.async_request_position(100)
        self.is_closing = False
        self.is_opening = True
        await self._roller.async_publish_updates()

        self._update_predicting_position()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Chiudi la tapparella."""
        await self._roller.async_request_position(0)
        self.is_opening = False
        self.is_closing = True
        await self._roller.async_publish_updates()

        self._update_predicting_position()

    def _update_predicting_position(self):
        self._cancel_predicting_position()
        self.task = self._loop.create_task(self.async_update_position())

    def _cancel_predicting_position(self):
        if self.task:
            self.task.cancel()

    async def async_update_position(self):
        """Update position while moving."""
        try:
            while self.is_opening or self.is_closing:
                _LOGGER.debug("Updating position loop start")

                await asyncio.sleep(1)
                if self.is_closing:
                    perc = round(100 / self._roller.total_down_time)
                    self.current_cover_position = max(
                        self.current_cover_position - perc, 0
                    )
                elif self.is_opening:
                    perc = 100 / self._roller.total_up_time
                    self.current_cover_position = min(
                        self.current_cover_position + perc, 100
                    )
                await self._roller.async_publish_updates()

            _LOGGER.debug("Updating position loop end")
        except asyncio.CancelledError:
            _LOGGER.debug("Updating position loop cancelled")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Ferma la tapparella."""
        self._cancel_predicting_position()

        await self._roller.async_stop()
        self.is_closed = self._roller.position == 0
        self.is_closing = False
        self.is_opening = False
        self.current_cover_position = self._roller.position
        await self._roller.async_publish_updates()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set position."""
        self._cancel_predicting_position()

        position = kwargs[ATTR_POSITION]
        await self._roller.async_request_position(position)

        if position > self.current_cover_position:
            self.is_opening = True
            self.is_closing = False
        else:
            self.is_closing = True
            self.is_opening = False

        self.current_cover_position = position
        await self._roller.async_publish_updates()
