"""
Support for interacting with Snapcast clients.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.snapcast/
"""
import asyncio
import logging
from os import path
import socket

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_SELECT_SOURCE,
    SERVICE_VOLUME_MUTE, SERVICE_SELECT_SOURCE, SERVICE_VOLUME_SET,
    PLATFORM_SCHEMA, ATTR_INPUT_SOURCE, ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDevice)
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_IDLE, STATE_PLAYING, STATE_UNKNOWN, CONF_HOST,
    CONF_PORT, ATTR_ENTITY_ID)
import homeassistant.helpers.config_validation as cv
from homeassistant.config import load_yaml_config_file

REQUIREMENTS = ['snapcast==2.0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'snapcast'

SERVICE_SNAPSHOT = 'snapcast_snapshot'
SERVICE_RESTORE = 'snapcast_restore'

SUPPORT_SNAPCAST_CLIENT = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET
SUPPORT_SNAPCAST_GROUP = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET |\
    SUPPORT_SELECT_SOURCE

GROUP_PREFIX = 'snapcast_group_'
GROUP_SUFFIX = 'Snapcast Group'
CLIENT_SUFFIX = 'Snapcast Client'

SERVICE_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Snapcast platform."""
    import snapcast.control
    from snapcast.control.server import CONTROL_PORT
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT, CONTROL_PORT)

    def _snapshot_service(service):
        """Snapshot current entity state."""
        entity_ids = service.data[ATTR_ENTITY_ID]
        for entity_id in entity_ids:
            if not hass.states.get(entity_id):
                continue
            state = hass.states.get(entity_id)
            input_source = state.attributes.get(ATTR_INPUT_SOURCE)
            volume_level = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
            volume_muted = state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            hass.data[DOMAIN][entity_id] = {
                ATTR_INPUT_SOURCE: input_source,
                ATTR_MEDIA_VOLUME_LEVEL: volume_level,
                ATTR_MEDIA_VOLUME_MUTED: volume_muted
            }

    def _restore_service(service):
        """Restore snapshotted entity state."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        for entity_id in entity_ids:
            if entity_id not in hass.data[DOMAIN]:
                continue
            data = hass.data[DOMAIN][entity_id]
            if data.get(ATTR_INPUT_SOURCE) is not None:
                attributes = {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_INPUT_SOURCE: data[ATTR_INPUT_SOURCE],
                }
                hass.services.call(
                    MEDIA_PLAYER_DOMAIN, SERVICE_SELECT_SOURCE, attributes)
            if data.get(ATTR_MEDIA_VOLUME_LEVEL) is not None:
                attributes = {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_MEDIA_VOLUME_LEVEL: data[ATTR_MEDIA_VOLUME_LEVEL]
                }
                hass.services.call(
                    MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET, attributes)
            if data.get(ATTR_MEDIA_VOLUME_MUTED) is not None:
                attributes = {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_MEDIA_VOLUME_MUTED: data[ATTR_MEDIA_VOLUME_MUTED]
                }
                hass.services.call(
                    MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_MUTE, attributes)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))
    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, _snapshot_service,
        descriptions.get(SERVICE_SNAPSHOT), schema=SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, _restore_service,
        descriptions.get(SERVICE_RESTORE), schema=SERVICE_SCHEMA)

    try:
        server = yield from snapcast.control.create_server(
            hass.loop, host, port)
    except socket.gaierror:
        _LOGGER.error('Could not connect to Snapcast server at %s:%d',
                      host, port)
        return False
    hass.data[DOMAIN] = {}
    async_add_devices([SnapcastClientDevice(client)
                       for client in server.clients])
    async_add_devices([SnapcastGroupDevice(group)
                       for group in server.groups])
    return True


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
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send the mute command."""
        yield from self._group.set_muted(mute)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set the volume level."""
        yield from self._group.set_volume(round(volume * 100))
        yield from self.async_update_ha_state()


class SnapcastClientDevice(MediaPlayerDevice):
    """Representation of a Snapcast client device."""

    def __init__(self, client):
        """Initialize the Snapcast client device."""
        client.set_callback(self.schedule_update_ha_state)
        self._client = client

    @property
    def name(self):
        """Return the name of the device."""
        return '{} {}'.format(self._client.friendly_name, CLIENT_SUFFIX)

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
    def should_poll(self):
        """Do not poll for state."""
        return False

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send the mute command."""
        yield from self._client.set_muted(mute)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set the volume level."""
        yield from self._client.set_volume(round(volume * 100))
        yield from self.async_update_ha_state()
