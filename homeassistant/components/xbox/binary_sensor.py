"""Xbox friends binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PresenceData, XboxConfigEntry, XboxUpdateCoordinator
from .entity import XboxBaseEntity


class XboxBinarySensor(StrEnum):
    """Xbox binary sensor."""

    ONLINE = "online"
    IN_PARTY = "in_party"
    IN_GAME = "in_game"
    IN_MULTIPLAYER = "in_multiplayer"


@dataclass(kw_only=True, frozen=True)
class XboxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Xbox binary sensor description."""

    is_on_fn: Callable[[PresenceData], bool | None]


SENSOR_DESCRIPTIONS: tuple[XboxBinarySensorEntityDescription, ...] = (
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.ONLINE,
        translation_key=XboxBinarySensor.ONLINE,
        is_on_fn=lambda x: x.online,
        name=None,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_PARTY,
        translation_key=XboxBinarySensor.IN_PARTY,
        is_on_fn=lambda x: x.in_party,
        entity_registry_enabled_default=False,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_GAME,
        translation_key=XboxBinarySensor.IN_GAME,
        is_on_fn=lambda x: x.in_game,
        entity_registry_enabled_default=False,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_MULTIPLAYER,
        translation_key=XboxBinarySensor.IN_MULTIPLAYER,
        is_on_fn=lambda x: x.in_multiplayer,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    coordinator = entry.runtime_data

    update_friends = partial(async_update_friends, coordinator, {}, async_add_entities)

    entry.async_on_unload(coordinator.async_add_listener(update_friends))

    update_friends()


class XboxBinarySensorEntity(XboxBaseEntity, BinarySensorEntity):
    """Representation of a Xbox presence state."""

    entity_description: XboxBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the status of the requested attribute."""

        return (
            self.entity_description.is_on_fn(self.data)
            if self.data is not None
            else None
        )


@callback
def async_update_friends(
    coordinator: XboxUpdateCoordinator,
    current: dict[str, list[XboxBinarySensorEntity]],
    async_add_entities,
) -> None:
    """Update friends."""
    new_ids = set(coordinator.data.presence)
    current_ids = set(current)

    # Process new favorites, add them to Home Assistant
    new_entities: list[XboxBinarySensorEntity] = []
    for xuid in new_ids - current_ids:
        current[xuid] = [
            XboxBinarySensorEntity(coordinator, xuid, description)
            for description in SENSOR_DESCRIPTIONS
        ]
        new_entities = new_entities + current[xuid]
    if new_entities:
        async_add_entities(new_entities)

    # Process deleted favorites, remove them from Home Assistant
    for xuid in current_ids - new_ids:
        coordinator.hass.async_create_task(
            async_remove_entities(xuid, coordinator, current)
        )


async def async_remove_entities(
    xuid: str,
    coordinator: XboxUpdateCoordinator,
    current: dict[str, list[XboxBinarySensorEntity]],
) -> None:
    """Remove friend sensors from Home Assistant."""
    registry = er.async_get(coordinator.hass)
    entities = current[xuid]
    for entity in entities:
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[xuid]
