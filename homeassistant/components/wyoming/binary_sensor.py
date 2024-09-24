"""Binary sensor for Wyoming."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WyomingSatelliteEntity

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.satellite is not None

    async_add_entities([WyomingSatelliteAssistInProgress(item.satellite.device)])


class WyomingSatelliteAssistInProgress(WyomingSatelliteEntity, BinarySensorEntity):
    """Entity to represent Assist is in progress for satellite."""

    entity_description = BinarySensorEntityDescription(
        entity_registry_enabled_default=False,
        key="assist_in_progress",
        translation_key="assist_in_progress",
    )
    _attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self._device.set_is_active_listener(self._is_active_changed)

    @callback
    def _is_active_changed(self) -> None:
        """Call when active state changed."""
        self._attr_is_on = self._device.is_active
        self.async_write_ha_state()
