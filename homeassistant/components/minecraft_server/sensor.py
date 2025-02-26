"""The Minecraft Server sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_TYPE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import MinecraftServerData, MinecraftServerType
from .const import KEY_LATENCY, KEY_MOTD
from .coordinator import MinecraftServerConfigEntry, MinecraftServerCoordinator
from .entity import MinecraftServerEntity

ATTR_PLAYERS_LIST = "players_list"

KEY_EDITION = "edition"
KEY_GAME_MODE = "game_mode"
KEY_MAP_NAME = "map_name"
KEY_PLAYERS_MAX = "players_max"
KEY_PLAYERS_ONLINE = "players_online"
KEY_PROTOCOL_VERSION = "protocol_version"
KEY_VERSION = "version"

UNIT_PLAYERS_MAX = "players"
UNIT_PLAYERS_ONLINE = "players"

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MinecraftServerSensorEntityDescription(SensorEntityDescription):
    """Class describing Minecraft Server sensor entities."""

    value_fn: Callable[[MinecraftServerData], StateType]
    attributes_fn: Callable[[MinecraftServerData], dict[str, Any]] | None
    supported_server_types: set[MinecraftServerType]


def get_extra_state_attributes_players_list(
    data: MinecraftServerData,
) -> dict[str, list[str]]:
    """Return players list as extra state attributes, if available."""
    extra_state_attributes: dict[str, Any] = {}
    players_list = data.players_list

    if players_list is not None and len(players_list) != 0:
        extra_state_attributes[ATTR_PLAYERS_LIST] = players_list

    return extra_state_attributes


SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_VERSION,
        translation_key=KEY_VERSION,
        value_fn=lambda data: data.version,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PROTOCOL_VERSION,
        translation_key=KEY_PROTOCOL_VERSION,
        value_fn=lambda data: data.protocol_version,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_MAX,
        translation_key=KEY_PLAYERS_MAX,
        native_unit_of_measurement=UNIT_PLAYERS_MAX,
        value_fn=lambda data: data.players_max,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
        },
        entity_registry_enabled_default=False,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_LATENCY,
        translation_key=KEY_LATENCY,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        value_fn=lambda data: data.latency,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MOTD,
        translation_key=KEY_MOTD,
        value_fn=lambda data: data.motd,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_ONLINE,
        translation_key=KEY_PLAYERS_ONLINE,
        native_unit_of_measurement=UNIT_PLAYERS_ONLINE,
        value_fn=lambda data: data.players_online,
        attributes_fn=get_extra_state_attributes_players_list,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_EDITION,
        translation_key=KEY_EDITION,
        value_fn=lambda data: data.edition,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.BEDROCK_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_GAME_MODE,
        translation_key=KEY_GAME_MODE,
        value_fn=lambda data: data.game_mode,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.BEDROCK_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MAP_NAME,
        translation_key=KEY_MAP_NAME,
        value_fn=lambda data: data.map_name,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.BEDROCK_EDITION,
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MinecraftServerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Minecraft Server sensor platform."""
    coordinator = config_entry.runtime_data

    # Add sensor entities.
    async_add_entities(
        [
            MinecraftServerSensorEntity(coordinator, description, config_entry)
            for description in SENSOR_DESCRIPTIONS
            if config_entry.data.get(CONF_TYPE, MinecraftServerType.JAVA_EDITION)
            in description.supported_server_types
        ]
    )


class MinecraftServerSensorEntity(MinecraftServerEntity, SensorEntity):
    """Representation of a Minecraft Server sensor base entity."""

    entity_description: MinecraftServerSensorEntityDescription

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
        description: MinecraftServerSensorEntityDescription,
        config_entry: MinecraftServerConfigEntry,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._update_properties()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_properties()
        self.async_write_ha_state()

    @callback
    def _update_properties(self) -> None:
        """Update sensor properties."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )

        if func := self.entity_description.attributes_fn:
            self._attr_extra_state_attributes = func(self.coordinator.data)
