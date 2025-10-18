"""Sensor platform for the Xbox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PresenceData, XboxConfigEntry, XboxUpdateCoordinator
from .entity import XboxBaseEntity


class XboxSensor(StrEnum):
    """Xbox sensor."""

    STATUS = "status"
    GAMER_SCORE = "gamer_score"
    ACCOUNT_TIER = "account_tier"
    GOLD_TENURE = "gold_tenure"


@dataclass(kw_only=True, frozen=True)
class XboxSensorEntityDescription(SensorEntityDescription):
    """Xbox sensor description."""

    value_fn: Callable[[PresenceData], StateType]


SENSOR_DESCRIPTIONS: tuple[XboxSensorEntityDescription, ...] = (
    XboxSensorEntityDescription(
        key=XboxSensor.STATUS,
        translation_key=XboxSensor.STATUS,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.status,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GAMER_SCORE,
        translation_key=XboxSensor.GAMER_SCORE,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.gamer_score,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.ACCOUNT_TIER,
        translation_key=XboxSensor.ACCOUNT_TIER,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.account_tier,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GOLD_TENURE,
        translation_key=XboxSensor.GOLD_TENURE,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.gold_tenure,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    coordinator = config_entry.runtime_data

    update_friends = partial(async_update_friends, coordinator, {}, async_add_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(update_friends))
    update_friends()


class XboxSensorEntity(XboxBaseEntity, SensorEntity):
    """Representation of a Xbox presence state."""

    entity_description: XboxSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the requested attribute."""
        return self.entity_description.value_fn(self.data) if self.data else None


@callback
def async_update_friends(
    coordinator: XboxUpdateCoordinator,
    current: dict[str, list[XboxSensorEntity]],
    async_add_entities,
) -> None:
    """Update friends."""
    new_ids = set(coordinator.data.presence)
    current_ids = set(current)

    # Process new favorites, add them to Home Assistant
    new_entities: list[XboxSensorEntity] = []
    for xuid in new_ids - current_ids:
        current[xuid] = [
            XboxSensorEntity(coordinator, xuid, description)
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
    current: dict[str, list[XboxSensorEntity]],
) -> None:
    """Remove friend sensors from Home Assistant."""
    registry = er.async_get(coordinator.hass)
    entities = current[xuid]
    for entity in entities:
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[xuid]
