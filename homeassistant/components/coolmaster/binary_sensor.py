"""Binary Sensor platform for CoolMasterNet integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import DATA_COORDINATOR, DATA_INFO, DOMAIN
from .entity import CoolmasterEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CoolMasterNet binary_sensor platform."""
    info = hass.data[DOMAIN][config_entry.entry_id][DATA_INFO]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        CoolmasterCleanFilter(coordinator, unit_id, info)
        for unit_id in coordinator.data
    )


class CoolmasterCleanFilter(CoolmasterEntity, BinarySensorEntity):
    """Representation of a unit's filter state (true means need to be cleaned)."""

    entity_description = BinarySensorEntityDescription(
        key="clean_filter",
        translation_key="clean_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._unit.clean_filter
