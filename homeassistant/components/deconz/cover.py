"""Support for deCONZ covers."""
from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_WINDOW,
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import COVER_TYPES, DAMPERS, NEW_LIGHT, WINDOW_COVERS
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up covers for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_cover(lights):
        """Add cover from deCONZ."""
        entities = []

        for light in lights:
            if (
                light.type in COVER_TYPES
                and light.uniqueid not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzCover(light, gateway))

        if entities:
            async_add_entities(entities)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_LIGHT), async_add_cover
        )
    )

    async_add_cover(gateway.api.lights.values())


class DeconzCover(DeconzDevice, CoverEntity):
    """Representation of a deCONZ cover."""

    TYPE = DOMAIN

    def __init__(self, device, gateway):
        """Set up cover device."""
        super().__init__(device, gateway)

        self._features = SUPPORT_OPEN
        self._features |= SUPPORT_CLOSE
        self._features |= SUPPORT_STOP
        self._features |= SUPPORT_SET_POSITION

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 100 - self._device.position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._device.is_open

    @property
    def device_class(self):
        """Return the class of the cover."""
        if self._device.type in DAMPERS:
            return "damper"
        if self._device.type in WINDOW_COVERS:
            return DEVICE_CLASS_WINDOW

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self._device.set_position(kwargs[ATTR_POSITION])

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        await self._device.open()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._device.close()

    async def async_stop_cover(self, **kwargs):
        """Stop cover."""
        await self._device.stop()
