"""YoLink Garage Door."""

from __future__ import annotations

from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import ATTR_DEVICE_FINGER, ATTR_GARAGE_DOOR_CONTROLLER

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up YoLink garage door from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    entities = [
        YoLinkCoverEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type
        in [ATTR_GARAGE_DOOR_CONTROLLER, ATTR_DEVICE_FINGER]
    ]
    async_add_entities(entities)


class YoLinkCoverEntity(YoLinkEntity, CoverEntity):
    """YoLink Cover Entity."""

    _attr_name = None

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink garage door entity."""
        super().__init__(config_entry, coordinator)
        self._attr_unique_id = f"{coordinator.device.device_id}_door_state"
        self._attr_device_class = CoverDeviceClass.GARAGE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        if (state_val := state.get("state")) is None:
            return
        if self.coordinator.paired_device is None or state_val == "error":
            self._attr_is_closed = None
            self._attr_available = False
            self.async_write_ha_state()
        elif state_val in ["open", "closed"]:
            self._attr_is_closed = state_val == "closed"
            self._attr_available = True
            self.async_write_ha_state()

    async def toggle_garage_state(self) -> None:
        """Toggle Garage door state."""
        # garage door state will not be changed by device call
        # it depends on paired device state, such as door sensor or contact sensor
        await self.call_device(ClientRequest("toggle", {}))

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Toggle garage door."""
        await self.toggle_garage_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Toggle garage door."""
        await self.toggle_garage_state()
