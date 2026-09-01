"""Cover platform for the VelaSmart integration."""

from typing import Any, override

from velasmart import VelaSmartApiClient

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VelasmartConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelasmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VelaSmart cover entities."""
    data = entry.runtime_data
    coordinator = data.coordinator
    client = data.client

    async_add_entities(
        VelaSmartCover(coordinator, client, device)
        for device in coordinator.data.values()
    )


class VelaSmartCover(CoordinatorEntity, CoverEntity):
    """Representation of a VelaSmart curtain."""

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_has_entity_name = True
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
        self._device_name: str = device["name"]
        self._attr_unique_id = device["id"]
        self._update_from_device(device)

    @property
    @override
    def device_info(self) -> DeviceInfo | None:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "VelaSmart",
            "model": "Smart Curtain",
        }

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.coordinator.data.get(self._device_id)
        if device is not None:
            self._update_from_device(device)
        super()._handle_coordinator_update()

    def _update_from_device(self, device: dict[str, Any]) -> None:
        """Update entity state from device data."""
        self._attr_current_cover_position = device.get("position")
        self._attr_is_closed = device.get("is_closed", False)
        self._attr_is_opening = False
        self._attr_is_closing = False

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the curtain."""
        await self._client.send_command(self._device_id, self._curtain_type, 100)
        self._attr_current_cover_position = 100
        self._attr_is_opening = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the curtain."""
        await self._client.send_command(self._device_id, self._curtain_type, 0)
        self._attr_current_cover_position = 0
        self._attr_is_closing = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the curtain position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return
        await self._client.send_command(self._device_id, self._curtain_type, position)
        self._attr_current_cover_position = position
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
