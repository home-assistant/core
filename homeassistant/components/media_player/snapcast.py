"""
Support for interacting with Snapcast clients.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.snapcast/
"""
import asyncio
import logging
import socket

import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN, PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, STATE_IDLE, STATE_OFF, STATE_ON,
    STATE_PLAYING, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['snapcast==2.0.8']

_LOGGER = logging.getLogger(__name__)

DATA_KEY = 'snapcast'

SERVICE_SNAPSHOT = 'snapcast_snapshot'
SERVICE_RESTORE = 'snapcast_restore'

SUPPORT_SNAPCAST_CLIENT = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET
SUPPORT_SNAPCAST_GROUP = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET |\
    SUPPORT_SELECT_SOURCE

GROUP_PREFIX = 'snapcast_group_'
GROUP_SUFFIX = 'Snapcast Group'
CLIENT_PREFIX = 'snapcast_client_'
CLIENT_SUFFIX = 'Snapcast Client'

SERVICE_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Snapcast platform."""
    import snapcast.control
    from snapcast.control.server import CONTROL_PORT
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT, CONTROL_PORT)

    @asyncio.coroutine
    def _handle_service(service):
        """Handle services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        devices = [device for device in hass.data[DATA_KEY]
                   if device.entity_id in entity_ids]
        for device in devices:
            if service.service == SERVICE_SNAPSHOT:
                device.snapshot()
            elif service.service == SERVICE_RESTORE:
                yield from device.async_restore()

    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, _handle_service, schema=SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, _handle_service, schema=SERVICE_SCHEMA)

    try:
        server = yield from snapcast.control.create_server(
            hass.loop, host, port, reconnect=True)
    except socket.gaierror:
        _LOGGER.error("Could not connect to Snapcast server at %s:%d",
                      host, port)
        return

    groups = [SnapcastGroupDevice(group) for group in server.groups]
    clients = [SnapcastClientDevice(client) for client in server.clients]
    devices = groups + clients
    hass.data[DATA_KEY] = devices
    async_add_devices(devices)


class SnapcastGroupDevice(MediaPlayerDevice):
    """Representation of a Snapcast group device."""

    def __init__(self, group):
        """Initialize the Snapcast group device."""
        group.set_callback(self.schedule_update_ha_state)
        self._group = group

    @property
    def state(self):
        """Return the state of the player."""
        return {
            'idle': STATE_IDLE,
            'playing': STATE_PLAYING,
            'unknown': STATE_UNKNOWN,
        }.get(self._group.stream_status, STATE_UNKNOWN)

    @property
    def name(self):
        """Return the name of the device."""
        return '{}{}'.format(GROUP_PREFIX, self._group.identifier)

    @property
    def source(self):
        """Return the current input source."""
        return self._group.stream

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._group.volume / 100

    @property
    def is_volume_muted(self):
        """Volume muted."""
        return self._group.muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SNAPCAST_GROUP

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._group.streams_by_name().keys())

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        name = '{} {}'.format(self._group.friendly_name, GROUP_SUFFIX)
        return {
            'friendly_name': name
        }

    @property
    def should_poll(self):
        """Do not poll for state."""
        return False

    @asyncio.coroutine
    def async_select_source(self, source):
        """Set input source."""
        streams = self._group.streams_by_name()
        if source in streams:
            yield from self._group.set_stream(streams[source].identifier)
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send the mute command."""
        yield from self._group.set_muted(mute)
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set the volume level."""
        yield from self._group.set_volume(round(volume * 100))
        self.async_schedule_update_ha_state()

    def snapshot(self):
        """Snapshot the group state."""
        self._group.snapshot()

    @asyncio.coroutine
    def async_restore(self):
        """Restore the group state."""
        yield from self._group.restore()


class SnapcastClientDevice(MediaPlayerDevice):
    """Representation of a Snapcast client device."""

    def __init__(self, client):
        """Initialize the Snapcast client device."""
        client.set_callback(self.schedule_update_ha_state)
        self._client = client

    @property
    def name(self):
        """Return the name of the device."""
        return '{}{}'.format(CLIENT_PREFIX, self._client.identifier)

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._client.volume / 100

    @property
    def is_volume_muted(self):
        """Volume muted."""
        return self._client.muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SNAPCAST_CLIENT

    @property
    def state(self):
        """Return the state of the player."""
        if self._client.connected:
            return STATE_ON
        return STATE_OFF

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        name = '{} {}'.format(self._client.friendly_name, CLIENT_SUFFIX)
        return {
            'friendly_name': name
        }

    @property
    def should_poll(self):
        """Do not poll for state."""
        return False

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send the mute command."""
        yield from self._client.set_muted(mute)
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set the volume level."""
        yield from self._client.set_volume(round(volume * 100))
        self.async_schedule_update_ha_state()

    def snapshot(self):
        """Snapshot the client state."""
        self._client.snapshot()

    @asyncio.coroutine
    def async_restore(self):
        """Restore the client state."""
        yield from self._client.restore()
