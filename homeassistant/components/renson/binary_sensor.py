"""Binary sensors for renson."""

from __future__ import annotations

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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RensonCoordinator
from .entity import RensonEntity


@dataclass(frozen=True, kw_only=True)
class RensonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of binary sensor."""

    field: FieldEnum


BINARY_SENSORS: tuple[RensonBinarySensorEntityDescription, ...] = (
    RensonBinarySensorEntityDescription(
        translation_key="frost_protection_active",
        key="FROST_PROTECTION_FIELD",
        field=FROST_PROTECTION_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="BREEZE_ENABLE_FIELD",
        translation_key="breeze",
        field=BREEZE_ENABLE_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="BREEZE_MET_FIELD",
        translation_key="breeze_conditions_met",
        field=BREEZE_MET_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="HUMIDITY_CONTROL_FIELD",
        translation_key="humidity_control",
        field=HUMIDITY_CONTROL_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="AIR_QUALITY_CONTROL_FIELD",
        translation_key="air_quality_control",
        field=AIR_QUALITY_CONTROL_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="CO2_CONTROL_FIELD",
        translation_key="co2_control",
        field=CO2_CONTROL_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RensonBinarySensorEntityDescription(
        key="PREHEATER_FIELD",
        translation_key="preheater",
        field=PREHEATER_FIELD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Call the Renson integration to setup."""

    api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id].api
    coordinator: RensonCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    async_add_entities(
        RensonBinarySensor(description, api, coordinator)
        for description in BINARY_SENSORS
    )


class RensonBinarySensor(RensonEntity, BinarySensorEntity):
    """Get sensor data from the Renson API and store it in the state of the class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        description: RensonBinarySensorEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__(description.key, api, coordinator)

        self.field = description.field
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        all_data = self.coordinator.data

        value = self.api.get_field_value(all_data, self.field.name)

        self._attr_is_on = self.api.parse_value(value, DataType.BOOLEAN)

        super()._handle_coordinator_update()
