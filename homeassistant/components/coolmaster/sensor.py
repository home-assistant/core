"""Sensor platform for CoolMasterNet integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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
    """Set up the CoolMasterNet sensor platform."""
    info = hass.data[DOMAIN][config_entry.entry_id][DATA_INFO]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        CoolmasterCleanFilter(coordinator, unit_id, info)
        for unit_id in coordinator.data
    )


class CoolmasterCleanFilter(CoolmasterEntity, SensorEntity):
    """Representation of a unit's error code."""

    entity_description = SensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    @property
    def native_value(self) -> str:
        """Return the error code or OK."""
        return self._unit.error_code or "OK"
