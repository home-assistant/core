"""YoLink Garage Door."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATORS, ATTR_GARAGE_DOOR_CONTROLLER, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink garage door from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATORS]
    entities = [
        YoLinkCoverEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type == ATTR_GARAGE_DOOR_CONTROLLER
    ]
    async_add_entities(entities)


class YoLinkCoverEntity(YoLinkEntity, CoverEntity):
    """YoLink Cover Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink garage door entity."""
        super().__init__(config_entry, coordinator)
        self._attr_unique_id = f"{coordinator.device.device_id}"
        self._attr_device_class = CoverDeviceClass.GARAGE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        self._attr_is_closed = state.get("state") == "closed"
        self.async_write_ha_state()

    async def toggle_garage_state(self, state: str) -> None:
        """Toggle Garage door state."""
        await self.call_device_api("toggle", {})

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open garage door."""
        await self.toggle_garage_state("open")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close garage door."""
        await self.toggle_garage_state("close")
