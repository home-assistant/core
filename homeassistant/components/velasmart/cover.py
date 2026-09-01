"""Cover platform for the VelaSmart integration."""

from __future__ import annotations

from typing import Any

from velasmart import VelaSmartApiClient

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VelaSmart cover entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client: VelaSmartApiClient = data["client"]

    async_add_entities(
        VelaSmartCover(coordinator, client, device)
        for device in coordinator.data.values()
    )


class VelaSmartCover(CoordinatorEntity, CoverEntity):
    """Representation of a VelaSmart curtain."""

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        coordinator: Any,
        client: VelaSmartApiClient,
        device: dict[str, Any],
    ) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator)
        self._client = client
        self._device_id: str = device["id"]
        self._curtain_type: int = device["device_type"]
        self._attr_unique_id = device["id"]
        self._attr_name = device["name"]
        self._update_from_device(device)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._attr_name,
            "manufacturer": "VelaSmart",
            "model": "Smart Curtain",
        }

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.coordinator.data.get(self._device_id)
        if device is not None:
            self._update_from_device(device)

    def _update_from_device(self, device: dict[str, Any]) -> None:
        """Update entity state from device data."""
        self._attr_current_cover_position = device.get("position")
        self._attr_is_closed = device.get("is_closed", False)
        self._attr_is_opening = False
        self._attr_is_closing = False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the curtain."""
        await self._client.send_command(self._device_id, self._curtain_type, 100)
        self._attr_current_cover_position = 100
        self._attr_is_opening = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the curtain."""
        await self._client.send_command(self._device_id, self._curtain_type, 0)
        self._attr_current_cover_position = 0
        self._attr_is_closing = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the curtain position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return
        await self._client.send_command(self._device_id, self._curtain_type, position)
        self._attr_current_cover_position = position
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
