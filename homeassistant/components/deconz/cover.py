"""Support for deCONZ covers."""
from homeassistant.components.cover import (
    ATTR_POSITION, CoverDevice, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_STOP,
    SUPPORT_SET_POSITION)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import COVER_TYPES, DAMPERS, NEW_LIGHT, WINDOW_COVERS
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

ZIGBEE_SPEC = ['lumi.curtain']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Unsupported way of setting up deCONZ covers."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up covers for deCONZ component.

    Covers are based on same device class as lights in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_cover(lights):
        """Add cover from deCONZ."""
        entities = []

        for light in lights:

            if light.type in COVER_TYPES:
                if light.modelid in ZIGBEE_SPEC:
                    entities.append(DeconzCoverZigbeeSpec(light, gateway))

                else:
                    entities.append(DeconzCover(light, gateway))

        async_add_entities(entities, True)

    gateway.listeners.append(async_dispatcher_connect(
        hass, gateway.async_event_new_device(NEW_LIGHT), async_add_cover))

    async_add_cover(gateway.api.lights.values())


class DeconzCover(DeconzDevice, CoverDevice):
    """Representation of a deCONZ cover."""

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
        if self.is_closed:
            return 0
        return int(self._device.brightness / 255 * 100)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._device.state

    @property
    def device_class(self):
        """Return the class of the cover."""
        if self._device.type in DAMPERS:
            return 'damper'
        if self._device.type in WINDOW_COVERS:
            return 'window'

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        data = {'on': False}
        if position > 0:
            data['on'] = True
            data['bri'] = int(position / 100 * 255)
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
        data = {'bri_inc': 0}
        await self._device.async_set_state(data)


class DeconzCoverZigbeeSpec(DeconzCover):
    """Zigbee spec is the inverse of how deCONZ normally reports attributes."""

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 100 - int(self._device.brightness / 255 * 100)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._device.state

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        data = {'on': False}
        if position < 100:
            data['on'] = True
            data['bri'] = 255 - int(position / 100 * 255)
        await self._device.async_set_state(data)
