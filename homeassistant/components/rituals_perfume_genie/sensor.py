"""Support for Rituals Perfume Genie sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyrituals import Diffuser

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity


@dataclass(frozen=True, kw_only=True)
class RitualsSensorEntityDescription(SensorEntityDescription):
    """Class describing Rituals sensor entities."""

    has_fn: Callable[[Diffuser], bool] = lambda _: True
    value_fn: Callable[[Diffuser], int | str]


ENTITY_DESCRIPTIONS = (
    RitualsSensorEntityDescription(
        key="battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda diffuser: diffuser.battery_percentage,
        has_fn=lambda diffuser: diffuser.has_battery,
    ),
    RitualsSensorEntityDescription(
        key="fill",
        translation_key="fill",
        value_fn=lambda diffuser: diffuser.fill,
    ),
    RitualsSensorEntityDescription(
        key="perfume",
        translation_key="perfume",
        value_fn=lambda diffuser: diffuser.perfume,
    ),
    RitualsSensorEntityDescription(
        key="wifi_percentage",
        translation_key="wifi_percentage",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda diffuser: diffuser.wifi_percentage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser sensors."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        RitualsSensorEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
        if description.has_fn(coordinator.diffuser)
    )


class RitualsSensorEntity(DiffuserEntity, SensorEntity):
    """Representation of a diffuser sensor."""

    entity_description: RitualsSensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | int:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.diffuser)
