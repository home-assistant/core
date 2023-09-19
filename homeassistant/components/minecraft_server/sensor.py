"""The Minecraft Server sensor platform."""
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
from .coordinator import MinecraftServerCoordinator, MinecraftServerData
from .entity import MinecraftServerEntity


@dataclass
class MinecraftServerEntityDescriptionMixin:
    """Mixin values for Minecraft Server entities."""

    value_fn: Callable[[MinecraftServerData], StateType]
    attributes_fn: Callable[[MinecraftServerData], MutableMapping[str, Any]] | None


@dataclass
class MinecraftServerSensorEntityDescription(
    SensorEntityDescription, MinecraftServerEntityDescriptionMixin
):
    """Class describing Minecraft Server sensor entities."""


def get_extra_state_attributes_players_list(
    data: MinecraftServerData,
) -> dict[str, list[str]]:
    """Return players list as extra state attributes, if available."""
    extra_state_attributes = {}
    players_list = data.players_list

    if players_list is not None and len(players_list) != 0:
        extra_state_attributes[ATTR_PLAYERS_LIST] = players_list

    return extra_state_attributes


SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_VERSION,
        translation_key=KEY_VERSION,
        icon=ICON_VERSION,
        value_fn=lambda data: data.version,
        attributes_fn=None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PROTOCOL_VERSION,
        translation_key=KEY_PROTOCOL_VERSION,
        icon=ICON_PROTOCOL_VERSION,
        value_fn=lambda data: data.protocol_version,
        attributes_fn=None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_MAX,
        translation_key=KEY_PLAYERS_MAX,
        native_unit_of_measurement=UNIT_PLAYERS_MAX,
        icon=ICON_PLAYERS_MAX,
        value_fn=lambda data: data.players_max,
        attributes_fn=None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_LATENCY,
        translation_key=KEY_LATENCY,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        icon=ICON_LATENCY,
        value_fn=lambda data: data.latency,
        attributes_fn=None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MOTD,
        translation_key=KEY_MOTD,
        icon=ICON_MOTD,
        value_fn=lambda data: data.motd,
        attributes_fn=None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_ONLINE,
        translation_key=KEY_PLAYERS_ONLINE,
        native_unit_of_measurement=UNIT_PLAYERS_ONLINE,
        icon=ICON_PLAYERS_ONLINE,
        value_fn=lambda data: data.players_online,
        attributes_fn=get_extra_state_attributes_players_list,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add sensor entities.
    async_add_entities(
        [
            MinecraftServerSensorEntity(coordinator, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class MinecraftServerSensorEntity(MinecraftServerEntity, SensorEntity):
    """Representation of a Minecraft Server sensor base entity."""

    entity_description: MinecraftServerSensorEntityDescription

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
        description: MinecraftServerSensorEntityDescription,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
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
