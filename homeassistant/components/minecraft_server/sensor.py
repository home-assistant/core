"""The Minecraft Server sensor platform."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.typing import HomeAssistantType

from . import MinecraftServer, MinecraftServerEntity
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


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Minecraft Server sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

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
    async_add_entities(entities, True)


class MinecraftServerStatusSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server status sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize status sensor."""
        super().__init__(hass, server, NAME_STATUS, unit=None, icon="mdi:lan")

    async def async_update(self) -> None:
        """Update status."""
        if self._server.online:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF


class MinecraftServerDescriptionSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server description sensor."""

    _COLOR_CODES = [
        "§0",
        "§1",
        "§2",
        "§3",
        "§4",
        "§5",
        "§6",
        "§7",
        "§8",
        "§9",
        "§a",
        "§b",
        "§c",
        "§d",
        "§e",
        "§f",
        "§k",
        "§l",
        "§m",
        "§n",
        "§o",
        "§r",
    ]

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize description sensor."""
        super().__init__(
            hass, server, NAME_DESCRIPTION, unit=None, icon="mdi:card-text"
        )

    async def async_update(self) -> None:
        """Update description."""
        description = self._server.description

        # Remove color codes.
        for color_code in self._COLOR_CODES:
            description = description.replace(color_code, "")

        # Remove newlines.
        description = description.replace("\n", " ")

        # Limit description length to 255.
        if len(description) > 255:
            description = description[:255]
            _LOGGER.debug("Description length > 255 (truncated).")

        self._state = description


class MinecraftServerVersionSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server version sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize version sensor."""
        super().__init__(hass, server, NAME_VERSION, unit=None, icon="mdi:numeric")

    async def async_update(self) -> None:
        """Update version."""
        self._state = self._server.version


class MinecraftServerProtocolVersionSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server protocol version sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize protocol version sensor."""
        super().__init__(
            hass, server, NAME_PROTOCOL_VERSION, unit=None, icon="mdi:numeric"
        )

    async def async_update(self) -> None:
        """Update protocol version."""
        self._state = self._server.protocol_version


class MinecraftServerLatencyTimeSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server latency time sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize latency time sensor."""
        super().__init__(hass, server, NAME_LATENCY_TIME, unit="ms", icon="mdi:signal")

    async def async_update(self) -> None:
        """Update latency time."""
        self._state = self._server.latency_time


class MinecraftServerPlayersOnlineSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server online players sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize online players sensor."""
        super().__init__(
            hass, server, NAME_PLAYERS_ONLINE, unit=None, icon="mdi:account-multiple"
        )

    async def async_update(self) -> None:
        """Update online players."""
        self._state = self._server.players_online


class MinecraftServerPlayersMaxSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server maximum number of players sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize maximum number of players sensor."""
        super().__init__(
            hass, server, NAME_PLAYERS_MAX, unit=None, icon="mdi:account-multiple"
        )

    async def async_update(self) -> None:
        """Update maximum number of players."""
        self._state = self._server.players_max


class MinecraftServerPlayersListSensor(MinecraftServerEntity):
    """Representation of a Minecraft Server players list sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize players list sensor."""
        super().__init__(
            hass, server, NAME_PLAYERS_LIST, unit=None, icon="mdi:account-multiple"
        )

    async def async_update(self) -> None:
        """Update players list."""
        players_list = self._server.players_list

        if not players_list:
            players_string = "[]"
        else:
            separator = ", "
            players_string = f"[{separator.join(players_list)}]"

            # Limit players list length to 255.
            if len(players_string) > 255:
                players_string = f"{players_string[:-4]}...]"
                _LOGGER.debug("Players list length > 255 (truncated).")

        self._state = players_string
