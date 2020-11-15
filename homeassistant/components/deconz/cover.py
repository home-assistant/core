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
    """Set up covers for deCONZ component.

    Covers are based on the same device class as lights in deCONZ.
    """
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
        return 100 - int(self._device.brightness / 254 * 100)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._device.state

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
        position = kwargs[ATTR_POSITION]
        data = {"on": False}

        if position < 100:
            data["on"] = True
            data["bri"] = 254 - int(position / 100 * 254)

        await self._device.async_set_state(data)

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        data = {ATTR_POSITION: 100}
        await self.async_set_cover_position(**data)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        data = {ATTR_POSITION: 0}
        await self.async_set_cover_position(**data)

    async def async_stop_cover(self, **kwargs):
        """Stop cover."""
        data = {"bri_inc": 0}
        await self._device.async_set_state(data)
