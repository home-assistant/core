"""Switch platform for Xthings Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import XthingsCloudCoordinator
from .entity import XthingsCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        XthingsCloudSwitch(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data.get("type") in ("switch", "plug")
        and "brightness" not in device_data.get("status", {})
    ]
    async_add_entities(entities)


class XthingsCloudSwitch(XthingsCloudEntity, SwitchEntity):
    """Xthings Cloud switch entity."""

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, device_id, device_data)
        self._device_type = device_data.get("type", "switch")

    @property
    def is_on(self) -> bool | None:
        return self.device_data.get("status", {}).get("on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._device_type == "plug":
            await self.coordinator.client.async_plug_on(self._device_id)
        else:
            await self.coordinator.client.async_switch_on(self._device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._device_type == "plug":
            await self.coordinator.client.async_plug_off(self._device_id)
        else:
            await self.coordinator.client.async_switch_off(self._device_id)
