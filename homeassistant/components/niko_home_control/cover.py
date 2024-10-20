"""Setup NikoHomeControlcover."""
from __future__ import annotations

import logging

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COVER_CLOSE, COVER_OPEN, COVER_STOP, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Niko Home Control cover."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    enabled_entities = hass.data[DOMAIN][entry.entry_id]["enabled_entities"]
    if enabled_entities["covers"] is False:
        return

    entities = []

    for action in hub.actions:
        _LOGGER.debug(action.name)
        action_type = action.action_type
        if action_type == 4:  # blinds/covers
            entity = NikoHomeControlCover(action, hub, options=entry.data["options"])
            hub.entities.append(entity)
            entities.append(entity)

    async_add_entities(entities, True)


class NikoHomeControlCover(CoverEntity):
    """Representation of a Niko Cover."""

    @property
    def should_poll(self) -> bool:
        """No polling needed for a Niko cover."""
        return False

    def __init__(self, cover, hub, options) -> None:
        """Set up the Niko Home Control cover."""
        self._cover = cover
        self._attr_unique_id = f"cover-{cover.action_id}"
        self._attr_name = cover.name
        self._moving = False
        if options["treatAsDevice"] is not False:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, self._attr_unique_id)},
                "manufacturer": "Niko",
                "name": cover.name,
                "model": "P.O.M",
                "suggested_area": cover.location,
                "via_device": hub._via_device,
            }

        else:
            self._attr_device_info = hub._device_info

    @property
    def id(self):
        """A Niko Action action_id."""
        return self._cover.action_id

    @property
    def supported_features(self):
        """Flag supported features."""
        return (
            CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN | CoverEntityFeature.STOP
        )

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._cover.state

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._cover.state == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._moving

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._moving

    @property
    def available(self) -> bool:
        """Return True if when available."""
        return True

    @property
    def is_open(self) -> bool:
        """Return if the cover is open, same as position 100."""
        return self._cover.state > 0

    def open_cover(self):
        """Open the cover."""
        _LOGGER.debug("Open cover: %s", self.name)
        # 255 = open
        self._cover.turn_on(COVER_OPEN)

    def close_cover(self):
        """Close the cover."""
        _LOGGER.debug("Close cover: %s", self.name)
        # 254 = close
        self._cover.turn_on(COVER_CLOSE)

    def stop_cover(self):
        """Stop the cover."""
        _LOGGER.debug("Stop cover: %s", self.name)
        # 253 = stop
        self._cover.turn_on(COVER_STOP)

    def update_state(self, state):
        """Update HA state."""
        _LOGGER.debug("Update state: %s", self.name)
        _LOGGER.debug("State: %s", state)
        self._cover.state = state
        self._attr_is_closed = state == 0
        self.async_write_ha_state()
