"""The Minecraft Server sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MinecraftServer, MinecraftServerData
from .const import (
    ATTR_PLAYERS_LIST,
    DOMAIN,
    ICON_LATENCY,
    ICON_MOTD,
    ICON_PLAYERS_MAX,
    ICON_PLAYERS_ONLINE,
    ICON_PROTOCOL_VERSION,
    ICON_VERSION,
    KEY_LATENCY,
    KEY_MOTD,
    KEY_PLAYERS_MAX,
    KEY_PLAYERS_ONLINE,
    KEY_PROTOCOL_VERSION,
    KEY_VERSION,
    UNIT_PLAYERS_MAX,
    UNIT_PLAYERS_ONLINE,
)
from .entity import MinecraftServerEntity


@dataclass
class MinecraftServerEntityDescriptionMixin:
    """Mixin values for Minecraft Server entities."""

    value_fn: Callable[[MinecraftServerData | None], StateType]


@dataclass
class MinecraftServerSensorEntityDescription(
    SensorEntityDescription, MinecraftServerEntityDescriptionMixin
):
    """Class describing Minecraft Server sensor entities."""


SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_VERSION,
        translation_key=KEY_VERSION,
        icon=ICON_VERSION,
        value_fn=lambda data: data.version if data else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PROTOCOL_VERSION,
        translation_key=KEY_PROTOCOL_VERSION,
        icon=ICON_PROTOCOL_VERSION,
        value_fn=lambda data: data.protocol_version if data else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_MAX,
        translation_key=KEY_PLAYERS_MAX,
        native_unit_of_measurement=UNIT_PLAYERS_MAX,
        icon=ICON_PLAYERS_MAX,
        value_fn=lambda data: data.players_max if data else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_LATENCY,
        translation_key=KEY_LATENCY,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        icon=ICON_LATENCY,
        value_fn=lambda data: data.latency if data else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MOTD,
        translation_key=KEY_MOTD,
        icon=ICON_MOTD,
        value_fn=lambda data: data.motd if data else None,
    ),
]

PLAYERS_ONLINE_SENSOR_DESCRIPTION = MinecraftServerSensorEntityDescription(
    key=KEY_PLAYERS_ONLINE,
    translation_key=KEY_PLAYERS_ONLINE,
    native_unit_of_measurement=UNIT_PLAYERS_ONLINE,
    icon=ICON_PLAYERS_ONLINE,
    value_fn=lambda data: data.players_online if data else None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server sensor platform."""
    server = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities list.
    entities = []

    for description in SENSOR_DESCRIPTIONS:
        entities.append(
            MinecraftServerSensorEntity(server=server, description=description)
        )

    entities.append(
        MinecraftServerPlayersOnlineSensor(
            server=server, description=PLAYERS_ONLINE_SENSOR_DESCRIPTION
        )
    )

    # Add sensor entities.
    async_add_entities(entities, True)


class MinecraftServerSensorEntity(MinecraftServerEntity, SensorEntity):
    """Representation of a Minecraft Server sensor base entity."""

    entity_description: MinecraftServerSensorEntityDescription

    def __init__(
        self,
        server: MinecraftServer,
        description: MinecraftServerSensorEntityDescription,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(server)
        self.entity_description = description
        self._attr_unique_id = f"{server.unique_id}-{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return self._server.online

    async def async_update(self) -> None:
        """Update sensor state."""
        self._attr_native_value = self.entity_description.value_fn(self._server.data)


class MinecraftServerPlayersOnlineSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server online players sensor."""

    _attr_translation_key = KEY_PLAYERS_ONLINE

    def __init__(
        self,
        server: MinecraftServer,
        description: MinecraftServerSensorEntityDescription,
    ) -> None:
        """Initialize online players sensor."""
        super().__init__(server=server, description=description)

    async def async_update(self) -> None:
        """Update online players state and device state attributes."""
        self._attr_native_value = self.entity_description.value_fn(self._server.data)

        extra_state_attributes = {}
        players_list = self._server.data.players_list

        if players_list is not None and len(players_list) != 0:
            extra_state_attributes[ATTR_PLAYERS_LIST] = players_list

        self._attr_extra_state_attributes = extra_state_attributes
