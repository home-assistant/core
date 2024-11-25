"""Support for Salda Smarty XP/XV Ventilation Unit Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pysmarty2 import Smarty

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartyConfigEntry, SmartyCoordinator
from .entity import SmartyEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SmartyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Smarty binary sensor entities."""

    value_fn: Callable[[Smarty], bool]


ENTITIES: tuple[SmartyBinarySensorEntityDescription, ...] = (
    SmartyBinarySensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda smarty: smarty.alarm,
    ),
    SmartyBinarySensorEntityDescription(
        key="warning",
        translation_key="warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda smarty: smarty.warning,
    ),
    SmartyBinarySensorEntityDescription(
        key="boost",
        translation_key="boost_state",
        value_fn=lambda smarty: smarty.boost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarty Binary Sensor Platform."""

    coordinator = entry.runtime_data

    async_add_entities(
        SmartyBinarySensor(coordinator, description) for description in ENTITIES
    )


class SmartyBinarySensor(SmartyEntity, BinarySensorEntity):
    """Representation of a Smarty Binary Sensor."""

    entity_description: SmartyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SmartyCoordinator,
        entity_description: SmartyBinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.client)
