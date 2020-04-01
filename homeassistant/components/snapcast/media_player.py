"""Support for interacting with Snapcast clients."""
import logging
import socket

import snapcast.control
from snapcast.control.server import CONTROL_PORT
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PLAYING,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    ATTR_MASTER,
    DOMAIN,
    SERVICE_JOIN,
    SERVICE_RESTORE,
    SERVICE_SNAPSHOT,
    SERVICE_UNJOIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "snapcast"

SUPPORT_SNAPCAST_CLIENT = (
    SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_SELECT_SOURCE
)
SUPPORT_SNAPCAST_GROUP = (
    SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_SELECT_SOURCE
)

GROUP_PREFIX = "snapcast_group_"
GROUP_SUFFIX = "Snapcast Group"
CLIENT_PREFIX = "snapcast_client_"
CLIENT_SUFFIX = "Snapcast Client"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_PORT): cv.port}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Snapcast platform."""

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT, CONTROL_PORT)

    async def async_service_handle(service_event, service, data):
        """Handle dispatched services."""
        entity_ids = data.get(ATTR_ENTITY_ID)
        devices = [
            device for device in hass.data[DATA_KEY] if device.entity_id in entity_ids
        ]
        for device in devices:
            if service == SERVICE_SNAPSHOT:
                device.snapshot()
            elif service == SERVICE_RESTORE:
                await device.async_restore()
            elif service == SERVICE_JOIN:
                if isinstance(device, SnapcastClientDevice):
                    master = [
                        e
                        for e in hass.data[DATA_KEY]
                        if e.entity_id == data[ATTR_MASTER]
                    ]
                    if isinstance(master[0], SnapcastClientDevice):
                        await device.async_join(master[0])
            elif service == SERVICE_UNJOIN:
                if isinstance(device, SnapcastClientDevice):
                    await device.async_unjoin()

        service_event.set()

    async_dispatcher_connect(hass, DOMAIN, async_service_handle)

    try:
        server = await snapcast.control.create_server(
            hass.loop, host, port, reconnect=True
        )
    except socket.gaierror:
        _LOGGER.error("Could not connect to Snapcast server at %s:%d", host, port)
        return

    # Note: Host part is needed, when using multiple snapservers
    hpid = f"{host}:{port}"

    groups = [SnapcastGroupDevice(group, hpid) for group in server.groups]
    clients = [SnapcastClientDevice(client, hpid) for client in server.clients]
    devices = groups + clients
    hass.data[DATA_KEY] = devices
    async_add_entities(devices)


class SnapcastGroupDevice(MediaPlayerDevice):
    """Representation of a Snapcast group device."""

    def __init__(self, group, uid_part):
        """Initialize the Snapcast group device."""
        group.set_callback(self.schedule_update_ha_state)
        self._group = group
        self._uid = f"{GROUP_PREFIX}{uid_part}_{self._group.identifier}"

    @property
    def state(self):
        """Return the state of the player."""
        return {
            "idle": STATE_IDLE,
            "playing": STATE_PLAYING,
            "unknown": STATE_UNKNOWN,
        }.get(self._group.stream_status, STATE_UNKNOWN)

    @property
    def unique_id(self):
        """Return the ID of snapcast group."""
        return self._uid

    @property
    def name(self):
        """Return the name of the device."""
        return f"{GROUP_PREFIX}{self._group.identifier}"

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
        name = f"{self._group.friendly_name} {GROUP_SUFFIX}"
        return {"friendly_name": name}

    @property
    def should_poll(self):
        """Do not poll for state."""
        return False

    async def async_select_source(self, source):
        """Set input source."""
        streams = self._group.streams_by_name()
        if source in streams:
            await self._group.set_stream(streams[source].identifier)
            self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Send the mute command."""
        await self._group.set_muted(mute)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level."""
        await self._group.set_volume(round(volume * 100))
        self.async_write_ha_state()

    def snapshot(self):
        """Snapshot the group state."""
        self._group.snapshot()

    async def async_restore(self):
        """Restore the group state."""
        await self._group.restore()


class SnapcastClientDevice(MediaPlayerDevice):
    """Representation of a Snapcast client device."""

    def __init__(self, client, uid_part):
        """Initialize the Snapcast client device."""
        client.set_callback(self.schedule_update_ha_state)
        self._client = client
        self._uid = f"{CLIENT_PREFIX}{uid_part}_{self._client.identifier}"

    @property
    def unique_id(self):
        """
        Return the ID of this snapcast client.

        Note: Host part is needed, when using multiple snapservers
        """
        return self._uid

    @property
    def identifier(self):
        """Return the snapcast identifier."""
        return self._client.identifier

    @property
    def name(self):
        """Return the name of the device."""
        return f"{CLIENT_PREFIX}{self._client.identifier}"

    @property
    def source(self):
        """Return the current input source."""
        return self._client.group.stream

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
    def source_list(self):
        """List of available input sources."""
        return list(self._client.group.streams_by_name().keys())

    @property
    def state(self):
        """Return the state of the player."""
        if self._client.connected:
            return STATE_ON
        return STATE_OFF

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        name = f"{self._client.friendly_name} {CLIENT_SUFFIX}"
        return {"friendly_name": name}

    @property
    def should_poll(self):
        """Do not poll for state."""
        return False

    async def async_select_source(self, source):
        """Set input source."""
        streams = self._client.group.streams_by_name()
        if source in streams:
            await self._client.group.set_stream(streams[source].identifier)
            self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Send the mute command."""
        await self._client.set_muted(mute)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level."""
        await self._client.set_volume(round(volume * 100))
        self.async_write_ha_state()

    async def async_join(self, master):
        """Join the group of the master player."""
        master_group = [
            group
            for group in self._client.groups_available()
            if master.identifier in group.clients
        ]
        await master_group[0].add_client(self._client.identifier)
        self.async_write_ha_state()

    async def async_unjoin(self):
        """Unjoin the group the player is currently in."""
        await self._client.group.remove_client(self._client.identifier)
        self.async_write_ha_state()

    def snapshot(self):
        """Snapshot the client state."""
        self._client.snapshot()

    async def async_restore(self):
        """Restore the client state."""
        await self._client.restore()
