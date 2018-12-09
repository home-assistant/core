"""
Support for deCONZ covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.deconz/
"""
from homeassistant.components.deconz.const import (
    COVER_TYPES, DAMPERS, DECONZ_REACHABLE, DOMAIN as DECONZ_DOMAIN,
    WINDOW_COVERS)
from homeassistant.components.cover import (
    ATTR_POSITION, CoverDevice, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_STOP,
    SUPPORT_SET_POSITION)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['deconz']

ZIGBEE_SPEC = ['lumi.curtain']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Unsupported way of setting up deCONZ covers."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up covers for deCONZ component.

    Covers are based on same device class as lights in deCONZ.
    """
    gateway = hass.data[DECONZ_DOMAIN]

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

    gateway.listeners.append(
        async_dispatcher_connect(hass, 'deconz_new_light', async_add_cover))

    async_add_cover(gateway.api.lights.values())


class DeconzCover(CoverDevice):
    """Representation of a deCONZ cover."""

    def __init__(self, cover, gateway):
        """Set up cover and add update callback to get data from websocket."""
        self._cover = cover
        self.gateway = gateway
        self.unsub_dispatcher = None

        self._features = SUPPORT_OPEN
        self._features |= SUPPORT_CLOSE
        self._features |= SUPPORT_STOP
        self._features |= SUPPORT_SET_POSITION

    async def async_added_to_hass(self):
        """Subscribe to covers events."""
        self._cover.register_async_callback(self.async_update_callback)
        self.gateway.deconz_ids[self.entity_id] = self._cover.deconz_id
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, DECONZ_REACHABLE, self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect cover object when removed."""
        if self.unsub_dispatcher is not None:
            self.unsub_dispatcher()
        self._cover.remove_callback(self.async_update_callback)
        self._cover = None

    @callback
    def async_update_callback(self, reason):
        """Update the cover's state."""
        self.async_schedule_update_ha_state()

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        if self.is_closed:
            return 0
        return int(self._cover.brightness / 255 * 100)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._cover.state

    @property
    def name(self):
        """Return the name of the cover."""
        return self._cover.name

    @property
    def unique_id(self):
        """Return a unique identifier for this cover."""
        return self._cover.uniqueid

    @property
    def device_class(self):
        """Return the class of the cover."""
        if self._cover.type in DAMPERS:
            return 'damper'
        if self._cover.type in WINDOW_COVERS:
            return 'window'

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def available(self):
        """Return True if light is available."""
        return self.gateway.available and self._cover.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        data = {'on': False}
        if position > 0:
            data['on'] = True
            data['bri'] = int(position / 100 * 255)
        await self._cover.async_set_state(data)

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
        await self._cover.async_set_state(data)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if (self._cover.uniqueid is None or
                self._cover.uniqueid.count(':') != 7):
            return None
        serial = self._cover.uniqueid.split('-', 1)[0]
        bridgeid = self.gateway.api.config.bridgeid
        return {
            'connections': {(CONNECTION_ZIGBEE, serial)},
            'identifiers': {(DECONZ_DOMAIN, serial)},
            'manufacturer': self._cover.manufacturer,
            'model': self._cover.modelid,
            'name': self._cover.name,
            'sw_version': self._cover.swversion,
            'via_hub': (DECONZ_DOMAIN, bridgeid),
        }


class DeconzCoverZigbeeSpec(DeconzCover):
    """Zigbee spec is the inverse of how deCONZ normally reports attributes."""

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 100 - int(self._cover.brightness / 255 * 100)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._cover.state

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        data = {'on': False}
        if position < 100:
            data['on'] = True
            data['bri'] = 255 - int(position / 100 * 255)
        await self._cover.async_set_state(data)
