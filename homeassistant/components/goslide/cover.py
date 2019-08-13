"""Support for Go Slide slides."""

import logging

from homeassistant.util import slugify
from homeassistant.components.cover import (
    ATTR_POSITION,
    ENTITY_ID_FORMAT,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    STATE_OPEN,
    STATE_CLOSED,
    DEVICE_CLASS_CURTAIN,
    CoverDevice,
)
from .const import API, DOMAIN, SLIDES

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up cover(s) for Go Slide platform."""
    entities = []

    for key in hass.data[DOMAIN][SLIDES]:
        _LOGGER.debug("Setting up GoSlide entity: %s", hass.data[DOMAIN][SLIDES][key])
        entities.append(GoSlideCover(hass, hass.data[DOMAIN][SLIDES][key]))

    async_add_entities(entities)


class GoSlideCover(CoverDevice):
    """Representation of a Go Slide cover."""

    def __init__(self, hass, slide):
        """Initialize the cover."""
        self._hass = hass
        self._mac = slide["mac"]
        self._id = slide["id"]
        self._name = slide["name"]
        self._entity_id = ENTITY_ID_FORMAT.format(slugify("goslide_" + self._mac))
        self._is_closed = None

    @property
    def entity_id(self):
        """Return the entity id of the cover."""
        return self._entity_id

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def state(self):
        """Return the state of the cover."""
        value = None

        if self._hass.data[DOMAIN][SLIDES][self._mac]["pos"] is not None:
            pos = int(self._hass.data[DOMAIN][SLIDES][self._mac]["pos"] * 100)
            if pos > 95:
                value = STATE_CLOSED
                if self._is_closed is None:
                    self._is_closed = True
            else:
                value = STATE_OPEN
                if self._is_closed is None:
                    self._is_closed = False

        return value

    @property
    def is_closed(self):
        """Return if the cover is closed. Used by cover.toggle."""
        return self._is_closed

    @property
    def assumed_state(self):
        """Let HA know the integration is assumed state."""
        return True

    @property
    def device_class(self):
        """Return the device class of the cover."""
        return DEVICE_CLASS_CURTAIN

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        if self._hass.data[DOMAIN][SLIDES][self._mac]["pos"] is None:
            pos = None
        else:
            pos = int(self._hass.data[DOMAIN][SLIDES][self._mac]["pos"] * 100)

        return pos

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._is_closed = False
        await self._hass.data[DOMAIN][API].slideopen(self._id)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._is_closed = True
        await self._hass.data[DOMAIN][API].slideclose(self._id)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._hass.data[DOMAIN][API].slidestop(self._id)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION] / 100

        if self._hass.data[DOMAIN][SLIDES][self._mac]["pos"] is not None:
            self._is_closed = (
                position > self._hass.data[DOMAIN][SLIDES][self._mac]["pos"]
            )

        await self._hass.data[DOMAIN][API].slidesetposition(self._id, position)
