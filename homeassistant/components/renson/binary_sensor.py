"""Binary sensors for renson."""
from dataclasses import dataclass

from renson_endura_delta.field_enum import (
    AIR_QUALITY_CONTROL_FIELD,
    BREEZE_ENABLE_FIELD,
    BREEZE_MET_FIELD,
    CO2_CONTROL_FIELD,
    FROST_PROTECTION_FIELD,
    HUMIDITY_CONTROL_FIELD,
    PREHEATER_FIELD,
    DataType,
    FieldEnum,
)
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .sensor import RensonCoordinator


@dataclass
class RensonBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    field: FieldEnum


@dataclass
class RensonBinarySensorEntityDescription(
    BinarySensorEntityDescription, RensonBinarySensorEntityDescriptionMixin
):
    """Description of binary sensor."""


BINARY_SENSORS: tuple[RensonBinarySensorEntityDescription, ...] = (
    RensonBinarySensorEntityDescription(
        name="Frost protection active",
        key="FROST_PROTECTION_FIELD",
        field=FROST_PROTECTION_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="BREEZE_ENABLE_FIELD",
        name="Breeze",
        field=BREEZE_ENABLE_FIELD,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="BREEZE_MET_FIELD",
        name="Breeze conditions met",
        field=BREEZE_MET_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="HUMIDITY_CONTROL_FIELD",
        name="Humidity control",
        field=HUMIDITY_CONTROL_FIELD,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="AIR_QUALITY_CONTROL_FIELD",
        name="Air quality control",
        field=AIR_QUALITY_CONTROL_FIELD,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="CO2_CONTROL_FIELD",
        name="CO2 control",
        field=CO2_CONTROL_FIELD,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="PREHEATER_FIELD",
        name="Preheater",
        field=PREHEATER_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


class RensonBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: RensonBinarySensorEntityDescription,
        renson_api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__(coordinator)
        self.renson = renson_api
        self.field = description.field
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        all_data = self.coordinator.data

        value = self.renson.get_field_value(all_data, self.field.name)

        self._attr_is_on = self.renson.parse_value(value, DataType.BOOLEAN)

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Call the Renson integration to setup."""
    renson_api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = RensonCoordinator(hass, renson_api)

    entities: list = []
    for description in BINARY_SENSORS:
        entities.append(RensonBinarySensor(description, renson_api, coordinator))

    async_add_entities(entities)
    await coordinator.async_config_entry_first_refresh()
