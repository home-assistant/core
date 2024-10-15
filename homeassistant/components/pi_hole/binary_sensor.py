"""Support for getting status from a Pi-hole system."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hole import Hole

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleConfigEntry
from .entity import PiHoleEntity


@dataclass(frozen=True, kw_only=True)
class PiHoleBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes PiHole binary sensor entity."""

    state_value: Callable[[Hole], bool]
    extra_value: Callable[[Hole], dict[str, Any] | None] = lambda api: None


BINARY_SENSOR_TYPES: tuple[PiHoleBinarySensorEntityDescription, ...] = (
    PiHoleBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_value=lambda api: bool(api.data.get("status") == "enabled"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Pi-hole binary sensor."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data

    binary_sensors = [
        PiHoleBinarySensor(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in BINARY_SENSOR_TYPES
    ]

    async_add_entities(binary_sensors, True)


class PiHoleBinarySensor(PiHoleEntity, BinarySensorEntity):
    """Representation of a Pi-hole binary sensor."""

    entity_description: PiHoleBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
        description: PiHoleBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""

        return self.entity_description.state_value(self.api)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the Pi-hole."""
        return self.entity_description.extra_value(self.api)
