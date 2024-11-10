"""Platform for eQ-3 binary sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from eq3btsmart import Thermostat

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_NAME_BATTERY,
    ENTITY_NAME_BUSY,
    ENTITY_NAME_CONNECTED,
    ENTITY_NAME_DST,
    ENTITY_NAME_WINDOW_OPEN,
)
from .entity import Eq3Entity, Eq3EntityDescription
from .models import Eq3Config, Eq3ConfigEntryData


@dataclass(frozen=True, kw_only=True)
class Eq3BinarySensorEntityDescription(
    Eq3EntityDescription, BinarySensorEntityDescription
):
    """Entity description for eQ-3 binary sensors."""

    value_func: Callable[[Thermostat], bool | None]


BINARY_SENSOR_ENTITY_DESCRIPTIONS = [
    Eq3BinarySensorEntityDescription(
        value_func=lambda thermostat: thermostat.is_busy,
        always_available=True,
        key=ENTITY_NAME_BUSY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_BUSY,
        entity_registry_enabled_default=False,
    ),
    Eq3BinarySensorEntityDescription(
        value_func=lambda thermostat: thermostat.is_connected,
        always_available=True,
        key=ENTITY_NAME_CONNECTED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_CONNECTED,
        entity_registry_enabled_default=False,
    ),
    Eq3BinarySensorEntityDescription(
        value_func=lambda thermostat: thermostat.status.is_low_battery
        if thermostat.status
        else None,
        key=ENTITY_NAME_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_BATTERY,
    ),
    Eq3BinarySensorEntityDescription(
        value_func=lambda thermostat: thermostat.status.is_window_open
        if thermostat.status
        else None,
        key=ENTITY_NAME_WINDOW_OPEN,
        device_class=BinarySensorDeviceClass.WINDOW,
        name=ENTITY_NAME_WINDOW_OPEN,
    ),
    Eq3BinarySensorEntityDescription(
        value_func=lambda thermostat: thermostat.status.is_dst
        if thermostat.status
        else None,
        key=ENTITY_NAME_DST,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=ENTITY_NAME_DST,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    eq3_config_entry: Eq3ConfigEntryData = hass.data[DOMAIN][config_entry.entry_id]
    entities_to_add: list[Entity] = [
        Eq3BinarySensorEntity(
            eq3_config_entry.eq3_config,
            eq3_config_entry.thermostat,
            entity_description,
        )
        for entity_description in BINARY_SENSOR_ENTITY_DESCRIPTIONS
    ]

    async_add_entities(entities_to_add)


class Eq3BinarySensorEntity(Eq3Entity, BinarySensorEntity):
    """Base class for eQ-3 binary sensor entities."""

    def __init__(
        self,
        eq3_config: Eq3Config,
        thermostat: Thermostat,
        entity_description: Eq3BinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(eq3_config, thermostat, entity_description)
        self.entity_description: Eq3BinarySensorEntityDescription = entity_description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""

        return self.entity_description.value_func(self._thermostat)
