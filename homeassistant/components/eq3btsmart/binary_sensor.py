"""Platform for eq3 binary sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from eq3btsmart.models import Status

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Eq3ConfigEntry
from .const import ENTITY_KEY_BATTERY, ENTITY_KEY_DST, ENTITY_KEY_WINDOW
from .entity import Eq3Entity


@dataclass(frozen=True, kw_only=True)
class Eq3BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity description for eq3 binary sensors."""

    value_func: Callable[[Status], bool]


BINARY_SENSOR_ENTITY_DESCRIPTIONS = [
    Eq3BinarySensorEntityDescription(
        value_func=lambda status: status.is_low_battery,
        key=ENTITY_KEY_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Eq3BinarySensorEntityDescription(
        value_func=lambda status: status.is_window_open,
        key=ENTITY_KEY_WINDOW,
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    Eq3BinarySensorEntityDescription(
        value_func=lambda status: status.is_dst,
        key=ENTITY_KEY_DST,
        translation_key=ENTITY_KEY_DST,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the entry."""

    async_add_entities(
        Eq3BinarySensorEntity(entry, entity_description)
        for entity_description in BINARY_SENSOR_ENTITY_DESCRIPTIONS
    )


class Eq3BinarySensorEntity(Eq3Entity, BinarySensorEntity):
    """Base class for eQ-3 binary sensor entities."""

    entity_description: Eq3BinarySensorEntityDescription

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        entity_description: Eq3BinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description.key)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""

        if TYPE_CHECKING:
            assert self._thermostat.status is not None

        return self.entity_description.value_func(self._thermostat.status)
