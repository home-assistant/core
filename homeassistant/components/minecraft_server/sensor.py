"""The Minecraft Server sensor platform."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import MinecraftServer, MinecraftServerEntity
from .const import (
    DOMAIN,
    ICON_DESCRIPTION,
    ICON_LATENCY_TIME,
    ICON_PLAYERS_LIST,
    ICON_PLAYERS_MAX,
    ICON_PLAYERS_ONLINE,
    ICON_PROTOCOL_VERSION,
    ICON_VERSION,
    NAME_DESCRIPTION,
    NAME_LATENCY_TIME,
    NAME_PLAYERS_LIST,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_PROTOCOL_VERSION,
    NAME_VERSION,
    UNIT_DESCRIPTION,
    UNIT_LATENCY_TIME,
    UNIT_PLAYERS_LIST,
    UNIT_PLAYERS_MAX,
    UNIT_PLAYERS_ONLINE,
    UNIT_PROTOCOL_VERSION,
    UNIT_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Minecraft Server sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [
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


class MinecraftServerSensorEntity(MinecraftServerEntity):
    """Representation of a Minecraft Server sensor base entity."""

    def __init__(
        self,
        hass: HomeAssistantType,
        server: MinecraftServer,
        type_name: str,
        icon: str = None,
        unit: str = None,
        device_class: str = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(hass, server, type_name, icon, device_class)
        self._state = None
        self._unit = unit

    @property
    def state(self) -> Any:
        """Return sensor state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return sensor measurement unit."""
        return self._unit


class MinecraftServerDescriptionSensor(MinecraftServerSensorEntity):
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
            hass=hass,
            server=server,
            type_name=NAME_DESCRIPTION,
            icon=ICON_DESCRIPTION,
            unit=UNIT_DESCRIPTION,
        )

    async def async_update(self) -> None:
        """Update description."""
        description = self._server.description

        if description is not None:
            # Remove color codes.
            for color_code in self._COLOR_CODES:
                description = description.replace(color_code, "")

            # Remove newlines.
            description = description.replace("\n", " ")

            # Limit description length to 255.
            if len(description) > 255:
                description = description[:255]
                _LOGGER.debug("Description length > 255 (truncated)")

        self._state = description


class MinecraftServerVersionSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server version sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize version sensor."""
        super().__init__(
            hass=hass,
            server=server,
            type_name=NAME_VERSION,
            icon=ICON_VERSION,
            unit=UNIT_VERSION,
        )

    async def async_update(self) -> None:
        """Update version."""
        self._state = self._server.version


class MinecraftServerProtocolVersionSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server protocol version sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize protocol version sensor."""
        super().__init__(
            hass=hass,
            server=server,
            type_name=NAME_PROTOCOL_VERSION,
            icon=ICON_PROTOCOL_VERSION,
            unit=UNIT_PROTOCOL_VERSION,
        )

    async def async_update(self) -> None:
        """Update protocol version."""
        self._state = self._server.protocol_version


class MinecraftServerLatencyTimeSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server latency time sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize latency time sensor."""
        super().__init__(
            hass=hass,
            server=server,
            type_name=NAME_LATENCY_TIME,
            icon=ICON_LATENCY_TIME,
            unit=UNIT_LATENCY_TIME,
        )

    async def async_update(self) -> None:
        """Update latency time."""
        self._state = self._server.latency_time


class MinecraftServerPlayersOnlineSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server online players sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize online players sensor."""
        super().__init__(
            hass=hass,
            server=server,
            type_name=NAME_PLAYERS_ONLINE,
            icon=ICON_PLAYERS_ONLINE,
            unit=UNIT_PLAYERS_ONLINE,
        )

    async def async_update(self) -> None:
        """Update online players."""
        self._state = self._server.players_online


class MinecraftServerPlayersMaxSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server maximum number of players sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize maximum number of players sensor."""
        super().__init__(
            hass=hass,
            server=server,
            type_name=NAME_PLAYERS_MAX,
            icon=ICON_PLAYERS_MAX,
            unit=UNIT_PLAYERS_MAX,
        )

    async def async_update(self) -> None:
        """Update maximum number of players."""
        self._state = self._server.players_max


class MinecraftServerPlayersListSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server players list sensor."""

    def __init__(self, hass: HomeAssistantType, server: MinecraftServer) -> None:
        """Initialize players list sensor."""
        super().__init__(
            hass=hass,
            server=server,
            type_name=NAME_PLAYERS_LIST,
            icon=ICON_PLAYERS_LIST,
            unit=UNIT_PLAYERS_LIST,
        )

    async def async_update(self) -> None:
        """Update players list."""
        players_list = self._server.players_list
        players_string = None

        if players_list is not None:
            if not players_list:
                players_string = "[]"
            else:
                separator = ", "
                players_string = f"[{separator.join(players_list)}]"

                # Limit players list length to 255.
                if len(players_string) > 255:
                    players_string = f"{players_string[:-4]}...]"
                    _LOGGER.debug("Players list length > 255 (truncated)")

        self._state = players_string
