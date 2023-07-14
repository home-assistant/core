"""Support for lights."""
from __future__ import annotations

from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import LIGHT, LIGHT_OFF, LIGHT_ON

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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

    devs = []
    for device in coordinator.devices:
        if device.type == LIGHT:
            devs.append(device)

    async_add_entities(ComelitLightEntity(coordinator, device) for device in devs)


class ComelitLightEntity(CoordinatorEntity[ComelitSerialBridge], LightEntity):
    """Light device."""

    _attr_has_entity_name = True

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

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.coordinator.async_add_listener(self._update_callback))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.coordinator.api.light_switch(self._device.index, LIGHT_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.light_switch(self._device.index, LIGHT_OFF)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._device.status == LIGHT_ON

    @property
    def name(self) -> str:
        """Return name of the light."""
        return self._device.name

    @property
    def available(self) -> bool:
        """Available."""
        return self.coordinator.last_update_success
