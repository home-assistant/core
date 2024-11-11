"""Platform for eq3 binary sensor entities."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Eq3ConfigEntry
from .const import (
    ENTITY_KEY_BATTERY,
    ENTITY_KEY_BUSY,
    ENTITY_KEY_CONNECTED,
    ENTITY_KEY_DST,
    ENTITY_KEY_WINDOW,
    ENTITY_NAME_BATTERY,
    ENTITY_NAME_CONNECTED,
    ENTITY_NAME_WINDOW,
    VALUE_KEY_BATTERY,
    VALUE_KEY_BUSY,
    VALUE_KEY_CONNECTED,
    VALUE_KEY_DST,
    VALUE_KEY_WINDOW,
)
from .entity import Eq3Entity


@dataclass(frozen=True, kw_only=True)
class Eq3BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity description for eq3 binary sensors."""

    value_key: str
    always_available: bool = False


BINARY_SENSOR_ENTITY_DESCRIPTIONS = [
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_BUSY,
        always_available=True,
        key=ENTITY_KEY_BUSY,
        translation_key=ENTITY_KEY_BUSY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_CONNECTED,
        always_available=True,
        key=ENTITY_KEY_CONNECTED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_CONNECTED,
        entity_registry_enabled_default=False,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_BATTERY,
        key=ENTITY_KEY_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_BATTERY,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_WINDOW,
        key=ENTITY_KEY_WINDOW,
        device_class=BinarySensorDeviceClass.WINDOW,
        name=ENTITY_NAME_WINDOW,
    ),
    Eq3BinarySensorEntityDescription(
        value_key=VALUE_KEY_DST,
        key=ENTITY_KEY_DST,
        translation_key=ENTITY_KEY_DST,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    async_add_entities(
        Eq3BinarySensorEntity(
            entry,
            entity_description,
        )
        for entity_description in BINARY_SENSOR_ENTITY_DESCRIPTIONS
    )


class Eq3BinarySensorEntity(Eq3Entity, BinarySensorEntity):
    """Base class for eQ-3 binary sensor entities."""

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        entity_description: Eq3BinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description.key)
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

    @callback
    def _async_on_disconnected(self) -> None:
        """Handle disconnection from the thermostat."""

        if not self.entity_description.always_available:
            self._attr_available = False

        self.async_write_ha_state()

    @callback
    def _async_on_connected(self) -> None:
        """Handle connection to the thermostat."""

        if not self.entity_description.always_available:
            self._attr_available = True

        self.async_write_ha_state()
