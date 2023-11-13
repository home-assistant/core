"""Support for V2C binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pytrydan import Trydan

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity


@dataclass
class V2CRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Trydan], bool]


@dataclass
class V2CBinarySensorEntityDescription(
    BinarySensorEntityDescription, V2CRequiredKeysMixin
):
    """Describes an EVSE binary sensor entity."""


TRYDAN_SENSORS = (
    V2CBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda evse: evse.connected,
    ),
    V2CBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda evse: evse.charging,
    ),
    V2CBinarySensorEntityDescription(
        key="ready",
        translation_key="ready",
        value_fn=lambda evse: evse.ready,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C binary sensor platform."""
    coordinator: V2CUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        V2CBinarySensorBaseEntity(coordinator, description, config_entry.entry_id)
        for description in TRYDAN_SENSORS
    )


class V2CBinarySensorBaseEntity(V2CBaseEntity, BinarySensorEntity):
    """Defines a base V2C binary_sensor entity."""

    entity_description: V2CBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CBinarySensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Init the V2C base entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the V2C binary_sensor."""
        return self.entity_description.value_fn(self.coordinator.evse)
