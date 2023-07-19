"""Support for lights."""
from __future__ import annotations

from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import LIGHT, LIGHT_OFF, LIGHT_ON

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit lights."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ComelitLightEntity(coordinator, device)
        for _, device in coordinator.data[LIGHT].items()
    )


class ComelitLightEntity(CoordinatorEntity[ComelitSerialBridge], LightEntity):
    """Light device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: ComelitSerialBridge, device: ComelitSerialBridgeObject
    ) -> None:
        """Init light entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.host}-light-{device.index}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self._attr_unique_id),
            },
            manufacturer="Comelit",
            model="Serial Bridge",
            name=device.name,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.coordinator.api.light_switch(self._device.index, LIGHT_ON)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.light_switch(self._device.index, LIGHT_OFF)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.data[LIGHT][self._device.index].status == LIGHT_ON
