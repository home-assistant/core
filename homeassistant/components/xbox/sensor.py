"""Xbox friends binary sensors."""
from __future__ import annotations

from functools import partial

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import XboxUpdateCoordinator
from .base_sensor import XboxBaseSensorEntity
from .const import DOMAIN

SENSOR_ATTRIBUTES = ["status", "gamer_score", "account_tier", "gold_tenure"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    coordinator: XboxUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    update_friends = partial(async_update_friends, coordinator, {}, async_add_entities)

    unsub = coordinator.async_add_listener(update_friends)
    hass.data[DOMAIN][config_entry.entry_id]["sensor_unsub"] = unsub
    update_friends()


class XboxSensorEntity(XboxBaseSensorEntity, SensorEntity):
    """Representation of a Xbox presence state."""

    @property
    def native_value(self):
        """Return the state of the requested attribute."""
        if not self.coordinator.last_update_success:
            return None

        return getattr(self.data, self.attribute, None)


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
            XboxSensorEntity(coordinator, xuid, attribute)
            for attribute in SENSOR_ATTRIBUTES
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
