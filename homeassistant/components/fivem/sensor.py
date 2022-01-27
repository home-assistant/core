"""The FiveM sensor platform."""
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FiveMEntity, FiveMServer
from .const import (
    ATTR_PLAYERS_LIST,
    ATTR_RESOURCES_LIST,
    DOMAIN,
    ICON_PLAYERS_MAX,
    ICON_PLAYERS_ONLINE,
    ICON_RESOURCES,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_RESOURCES,
    UNIT_PLAYERS_MAX,
    UNIT_PLAYERS_ONLINE,
    UNIT_RESOURCES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server sensor platform."""
    server = hass.data[DOMAIN][entry.entry_id]

    # Create entities list.
    entities = [
        FiveMPlayersOnlineSensor(server),
        FiveMPlayersMaxSensor(server),
        FiveMResourcesSensor(server),
    ]

    # Add sensor entities.
    async_add_entities(entities, True)


class FiveMSensorEntity(FiveMEntity, SensorEntity):
    """Representation of a FiveM sensor base entity."""

    def __init__(
        self,
        server: FiveMServer,
        type_name: str,
        icon: str,
        unit: str,
        device_class: str = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(server, type_name, icon, device_class)
        self._state: Any = None
        self._unit = unit

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return self._fivem.online

    @property
    def native_value(self):
        """Return sensor state."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return sensor measurement unit."""
        return self._unit


class FiveMPlayersOnlineSensor(FiveMSensorEntity):
    """Representation of a FiveM online players sensor."""

    def __init__(
        self,
        server: FiveMServer,
    ) -> None:
        """Initialize online players sensor."""
        super().__init__(
            server, NAME_PLAYERS_ONLINE, ICON_PLAYERS_ONLINE, UNIT_PLAYERS_ONLINE
        )
        self._extra_state_attributes: dict[str, Any] = {}

    async def async_update(self) -> None:
        """Update online players state and device attributes."""
        self._state = self._fivem.players_online

        extra_state_attributes = {}
        players_list = self._fivem.players_list

        if len(players_list) != 0:
            extra_state_attributes = {ATTR_PLAYERS_LIST: players_list}

        self._extra_state_attributes = extra_state_attributes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return players list in device attributes."""
        return self._extra_state_attributes


class FiveMPlayersMaxSensor(FiveMSensorEntity):
    """Representation of a FiveM maximum number of players sensor."""

    def __init__(self, server: FiveMServer) -> None:
        """Initialize maximum number of players sensor."""
        super().__init__(
            server=server,
            type_name=NAME_PLAYERS_MAX,
            icon=ICON_PLAYERS_MAX,
            unit=UNIT_PLAYERS_MAX,
        )

    async def async_update(self) -> None:
        """Update maximum number of players."""
        self._state = self._fivem.players_max


class FiveMResourcesSensor(FiveMSensorEntity):
    """Representation of a FiveM resources sensor."""

    def __init__(
        self,
        server: FiveMServer,
    ) -> None:
        """Initialize resources sensor."""
        super().__init__(server, NAME_RESOURCES, ICON_RESOURCES, UNIT_RESOURCES)
        self._extra_state_attributes: dict[str, Any] = {}

    async def async_update(self) -> None:
        """Update resources state and state attributes."""
        self._state = self._fivem.resources_count

        extra_state_attributes = {}
        resources_list = self._fivem.resources_list

        if len(resources_list) != 0:
            extra_state_attributes = {ATTR_RESOURCES_LIST: resources_list}

        self._extra_state_attributes = extra_state_attributes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return resources list in state attributes."""
        return self._extra_state_attributes
