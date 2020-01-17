"""The Minecraft Server sensor platform."""

import logging

from homeassistant.const import CONF_NAME, STATE_ON, STATE_UNAVAILABLE

from . import MinecraftServerEntity
from .const import (
    DOMAIN,
    NAME_DESCRIPTION,
    NAME_LATENCY_TIME,
    NAME_PLAYERS_LIST,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_PROTOCOL_VERSION,
    NAME_STATUS,
    NAME_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Minecraft Server sensor platform."""
    _LOGGER.debug("Setting up platform...")

    server = hass.data[DOMAIN][config_entry.data[CONF_NAME]]

    # Create entities list.
    entities = [
        MinecraftServerStatusSensor(hass, server),
        MinecraftServerDescriptionSensor(hass, server),
        MinecraftServerVersionSensor(hass, server),
        MinecraftServerProtocolVersionSensor(hass, server),
        MinecraftServerLatencyTimeSensor(hass, server),
        MinecraftServerPlayersOnlineSensor(hass, server),
        MinecraftServerPlayersMaxSensor(hass, server),
        MinecraftServerPlayersListSensor(hass, server),
    ]

    # Add sensor entities.
    _LOGGER.debug("Adding sensor entities...")
    async_add_entities(entities, True)

    _LOGGER.debug("Platform setup finished.")


class MinecraftServerStatusSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server status sensor."""

    def __init__(self, hass, server):
        """Initialize status sensor."""
        super().__init__(hass, server, NAME_STATUS, unit=None, icon="mdi:lan")

    async def async_update(self):
        """Update status."""
        state = None
        if self._server.online() is True:
            state = STATE_ON
        else:
            state = STATE_UNAVAILABLE
        self._state = state


class MinecraftServerDescriptionSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server description sensor."""

    def __init__(self, hass, server):
        """Initialize description sensor."""
        super().__init__(
            hass, server, NAME_DESCRIPTION, unit=None, icon="mdi:card-text"
        )

    async def async_update(self):
        """Update description."""
        self._state = self._server.description()


class MinecraftServerVersionSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server version sensor."""

    def __init__(self, hass, server):
        """Initialize version sensor."""
        super().__init__(hass, server, NAME_VERSION, unit=None, icon="mdi:numeric")

    async def async_update(self):
        """Update version."""
        self._state = self._server.version()


class MinecraftServerProtocolVersionSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server protocol version sensor."""

    def __init__(self, hass, server):
        """Initialize protocol version sensor."""
        super().__init__(
            hass, server, NAME_PROTOCOL_VERSION, unit=None, icon="mdi:numeric"
        )

    async def async_update(self):
        """Update protocol version."""
        self._state = self._server.protocol_version()


class MinecraftServerLatencyTimeSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server latency time sensor."""

    def __init__(self, hass, server):
        """Initialize latency time sensor."""
        super().__init__(hass, server, NAME_LATENCY_TIME, unit="ms", icon="mdi:signal")

    async def async_update(self):
        """Update latency time."""
        self._state = self._server.latency_time()


class MinecraftServerPlayersOnlineSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server online players sensor."""

    def __init__(self, hass, server):
        """Initialize online players sensor."""
        super().__init__(
            hass, server, NAME_PLAYERS_ONLINE, unit=None, icon="mdi:account-multiple"
        )

    async def async_update(self):
        """Update online players."""
        self._state = self._server.players_online()


class MinecraftServerPlayersMaxSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server maximum number of players sensor."""

    def __init__(self, hass, server):
        """Initialize maximum number of players sensor."""
        super().__init__(
            hass, server, NAME_PLAYERS_MAX, unit=None, icon="mdi:account-multiple"
        )

    async def async_update(self):
        """Update maximum number of players."""
        self._state = self._server.players_max()


class MinecraftServerPlayersListSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server players list sensor."""

    def __init__(self, hass, server):
        """Initialize players list sensor."""
        super().__init__(
            hass, server, NAME_PLAYERS_LIST, unit=None, icon="mdi:account-multiple"
        )

    async def async_update(self):
        """Update players list."""
        self._state = self._server.players_list()
