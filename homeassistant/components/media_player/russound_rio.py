"""
Support for interfacing with Russound via RIO Protocol.

The RIO protocol is supported by newer Russound devices such as the MCA-88.

The platform will discover all enabled zones and sources and only needs to be
provided with a name and host. It can optionally be provided with a port,
though this should always be 9621 on any standard Russound configuration.

An example configuration.yaml entry looks like this:

media_player:
  platform: russound_rio
  host: 192.168.1.100
  port: 9621
  name: Russound Controller

Each zone is added as a separate media player device. If the source that the
zone is assigned to is capable of sending metadata such as artist/album name
then this data will be reported back via the media_* properties.
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.media_player import (
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice, PLATFORM_SCHEMA,
    MEDIA_TYPE_MUSIC)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON,
    CONF_NAME, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['russound_rio==0.1.1']

_LOGGER = logging.getLogger(__name__)

SUPPORT_RUSSOUND = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                   SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_PORT, default=9621): cv.port,
    })


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Russound RIO platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    if host is None or port is None:
        _LOGGER.error("Invalid config. Expected %s and %s",
                      CONF_HOST, CONF_PORT)
        return False

    from russound_rio import Russound, CommandException, ZoneID

    russ = Russound(hass.loop, host, port)

    yield from russ.connect()

    # Discover sources
    sources = []
    for source_id in range(1, 17):
        try:
            name = yield from russ.get_source_variable(source_id, 'name')
        except CommandException:
            break
        if name != '':
            sources.append((source_id, name))

    # Discover zones
    valid_zones = []

    @asyncio.coroutine
    def try_watch_zone(zone_id):
        """
        Set a watch on a zone.

        Return the zone_id one success, otherwise return None.
        """
        try:
            yield from russ.watch_zone(zone_id)
            return zone_id
        except CommandException:
            return None

    for controller in range(1, 17):
        futures = [try_watch_zone(ZoneID(x, controller))
                   for x in range(1, 17)]
        results = yield from asyncio.gather(*futures)
        if any(results):
            valid_zones.extend([x for x in results if x])
        else:
            break

    devices = []
    for zone_id in valid_zones:
        name = yield from russ.get_zone_variable(zone_id, 'name')
        if name:
            dev = RussoundZoneDevice(russ, zone_id, name, sources)
            devices.append(dev)

    @callback
    def on_stop(event):
        """Shutdown cleanly when hass stops."""
        hass.loop.create_task(russ.close())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)

    async_add_devices(devices)


class RussoundZoneDevice(MediaPlayerDevice):
    """Representation of a Russound Zone."""

    def _zone_var(self, name, default=None):
        return self._russ.get_cached_zone_variable(self._zone_id,
                                                   name,
                                                   default)

    def _source_var(self, name, default=None):
        current = int(self._zone_var('currentsource', 0))
        if current:
            return self._russ.get_cached_source_variable(
                current, name, default)
        return default

    def _source_na_var(self, name):
        """Will replace invalid values with None."""
        current = int(self._zone_var('currentsource', 0))
        if current:
            value = self._russ.get_cached_source_variable(
                current, name, None)
            if value is None:
                return None
            if value == "":
                return None
            if value == "------":
                return None
            return value
        else:
            return None

    def __init__(self, russ, zone_id, name, sources):
        """Initialize the zone device."""
        super().__init__()
        self._name = name
        self._russ = russ
        self._zone_id = zone_id
        self._sources = sources
        self._russ.add_zone_callback(self._zone_callback_handler)
        self._russ.add_source_callback(self._source_callback_handler)

    def _zone_callback_handler(self, zone_id, *args):
        if zone_id == self._zone_id:
            self.schedule_update_ha_state()

    def _source_callback_handler(self, source_id, *args):
        current = int(self._zone_var('currentsource', 0))
        if source_id == current:
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the zone."""
        return self._zone_var('name', self._name)

    @property
    def state(self):
        """Return the state of the device."""
        status = self._zone_var('status', "OFF")
        if status == 'ON':
            return STATE_ON
        elif status == 'OFF':
            return STATE_OFF

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_RUSSOUND

    @property
    def source(self):
        """Get the currently selected source."""
        return self._source_na_var('name')

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return [x[1] for x in self._sources]

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._source_na_var('songname')

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._source_na_var('artistname')

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._source_na_var('albumname')

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._source_na_var('coverarturl')

    @property
    def volume_level(self):
        """Volume level of the media player (0..1).

        Value is returned based on a range (0..50).
        Therefore float divide by 50 to get to the required range.
        """
        return float(self._zone_var('volume', 0)) / 50.0

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn off the zone."""
        yield from self._russ.send_zone_event(self._zone_id,
                                              "ZoneOff")

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn on the zone."""
        yield from self._russ.send_zone_event(self._zone_id,
                                              "ZoneOn")

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set the volume level."""
        rvol = int(volume * 50.0)
        yield from self._russ.send_zone_event(self._zone_id,
                                              "KeyPress",
                                              "Volume",
                                              rvol)

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select the source input for this zone."""
        for source_id, name in self._sources:
            if name.lower() != source.lower():
                continue
            yield from self._russ.send_zone_event(
                self._zone_id, "SelectSource", source_id)
