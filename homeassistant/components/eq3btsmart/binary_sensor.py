"""Platform for eQ-3 binary sensor entities."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Eq3ConfigEntry
from .const import (
    ENTITY_NAME_BATTERY,
    ENTITY_NAME_BUSY,
    ENTITY_NAME_CONNECTED,
    ENTITY_NAME_DST,
    ENTITY_NAME_WINDOW_OPEN,
    TRANSLATION_KEY_BUSY,
    TRANSLATION_KEY_DST,
    VALUE_KEY_BUSY,
    VALUE_KEY_CONNECTED,
    VALUE_KEY_DST,
    VALUE_KEY_LOW_BATTERY,
    VALUE_KEY_WINDOW_OPEN,
)
from .entity import Eq3Entity, Eq3EntityDescription


@dataclass(frozen=True, kw_only=True)
class Eq3BinarySensorEntityDescription(
    Eq3EntityDescription, BinarySensorEntityDescription
):
    """Entity description for eQ-3 binary sensors."""

    value_key: str


BINARY_SENSOR_ENTITY_DESCRIPTIONS = [
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_BUSY,
        always_available=True,
        key=ENTITY_NAME_BUSY,
        translation_key=TRANSLATION_KEY_BUSY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_BUSY,
        entity_registry_enabled_default=False,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_CONNECTED,
        always_available=True,
        key=ENTITY_NAME_CONNECTED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_CONNECTED,
        entity_registry_enabled_default=False,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_LOW_BATTERY,
        key=ENTITY_NAME_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_BATTERY,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_WINDOW_OPEN,
        key=ENTITY_NAME_WINDOW_OPEN,
        device_class=BinarySensorDeviceClass.WINDOW,
        name=ENTITY_NAME_WINDOW_OPEN,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_DST,
        key=ENTITY_NAME_DST,
        translation_key=TRANSLATION_KEY_DST,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_DST,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    entities_to_add: list[Entity] = [
        Eq3BinarySensorEntity(
            entry,
            entity_description,
        )
        for entity_description in BINARY_SENSOR_ENTITY_DESCRIPTIONS
    ]

    async_add_entities(entities_to_add)


class Eq3BinarySensorEntity(Eq3Entity, BinarySensorEntity):
    """Base class for eQ-3 binary sensor entities."""

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        entity_description: Eq3BinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description)
        self.entity_description: Eq3BinarySensorEntityDescription = entity_description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""

        state: Any = None

        if hasattr(self._thermostat, self.entity_description.value_key):
            state = getattr(self._thermostat, self.entity_description.value_key)

        if self._thermostat.status is not None and hasattr(
            self._thermostat.status, self.entity_description.value_key
        ):
            state = getattr(self._thermostat.status, self.entity_description.value_key)

        if not isinstance(state, bool | None):
            return None

        return state
