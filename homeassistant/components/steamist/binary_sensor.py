"""Support for Steamist binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import SteamistEntity

ACTIVE_SENSOR = BinarySensorEntityDescription(
    key="active", icon="mdi:pot-steam", name="Steam Active"
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [SteamistBinarySensorEntity(coordinator, config_entry, ACTIVE_SENSOR)]
    )


class SteamistBinarySensorEntity(SteamistEntity, BinarySensorEntity):
    """Representation of an Steamist binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        return self._status.active
