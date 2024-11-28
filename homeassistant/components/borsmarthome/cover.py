import logging
from typing import Any

import requests

# import voluptuous as vol
from homeassistant.components.borsmarthome.hub import RollerShutter
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import HubConfigEntry

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
    async_add_entities(TapparellaEntity(roller) for roller in hub.devices)


class TapparellaEntity(CoverEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.SHUTTER
    unsub = None

    def set_current_position(self, position: float):
        """Set position."""
        self.is_closed = position == 0
        self.current_cover_position = position

    async def async_on_change(self, event: Event[EventStateChangedData]) -> None:
        """On change callback."""
        new_state = event.data["new_state"]

        current_position = new_state.attributes.get("currentPosition")
        if current_position:
            self.set_current_position(current_position)

        is_opening = new_state.attributes.get("isOpening")
        if is_opening is not None:
            self.is_opening = is_opening

        is_closing = new_state.attributes.get("isClosing")
        if is_closing is not None:
            self.is_closing = is_closing

        await self._roller.async_publish_updates()

    async def async_will_remove_from_hass(self):
        """On remove from hass."""
        self.unsub()
        self._roller.remove_callback(self.async_write_ha_state)

    async def async_added_to_hass(self):
        """On add to hass."""
        self.unsub = async_track_state_change_event(
            self.hass, self.entity_id, self.async_on_change
        )
        self._roller.register_callback(self.async_write_ha_state)

    def __init__(self, roller: RollerShutter):
        """Initialize the entity."""
        self._name = roller.name
        self._roller = roller
        self._channel = roller.name
        self.set_current_position(roller.position)
        self.unique_id = f"avebus_{roller.name}"

    @property
    def name(self):
        return self._name

    @property
    def position(self):
        return self.current_cover_position

    @property
    def channel(self):
        return self._channel

    @property
    def supported_features(self):
        """Get supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_open_cover(self, **kwargs: Any):
        """Apri la tapparella."""
        try:
            await self._roller.async_request_position(100)
            self.is_opening = True
            await self._roller.async_publish_updates()
        except requests.RequestException as e:
            _LOGGER.error("Errore durante l'apertura della tapparella: %s", e)

    async def async_close_cover(self, **kwargs: Any):
        """Chiudi la tapparella."""
        try:
            await self._roller.async_request_position(0)
            self.is_closing = True
            await self._roller.async_publish_updates()
        except requests.RequestException as e:
            _LOGGER.error("Errore durante la chiusura della tapparella: %s", e)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Ferma la tapparella."""
        try:
            await self._roller.async_stop()
            self.is_closed = self._roller.position == 0
            self.is_closing = False
            self.is_opening = False
            self.current_cover_position = self._roller.position
            await self._roller.async_publish_updates()
        except requests.RequestException as e:
            _LOGGER.error("Errore durante il fermo della tapparella: %s", e)

    async def async_set_cover_position(self, **kwargs):
        """Set position."""
        try:
            position = kwargs["position"]
            await self._roller.async_request_position(position)

            if position > self.current_cover_position:
                self.is_opening = True
            else:
                self.is_closing = True

            await self._roller.async_publish_updates()
        except requests.RequestException as e:
            _LOGGER.error("Errore durante il set della tapparella: %s", e)
