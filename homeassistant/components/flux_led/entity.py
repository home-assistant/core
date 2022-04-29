"""Support for Magic Home lights."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from flux_led.aiodevice import AIOWifiLedBulb

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_HW_VERSION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MINOR_VERSION, DOMAIN, SIGNAL_STATE_UPDATED
from .coordinator import FluxLedUpdateCoordinator


def _async_device_info(
    device: AIOWifiLedBulb, entry: config_entries.ConfigEntry
) -> DeviceInfo:
    version_num = device.version_num
    if minor_version := entry.data.get(CONF_MINOR_VERSION):
        sw_version = version_num + int(hex(minor_version)[2:]) / 100
        sw_version_str = f"{sw_version:0.2f}"
    else:
        sw_version_str = str(device.version_num)
    device_info: DeviceInfo = {
        ATTR_IDENTIFIERS: {(DOMAIN, entry.entry_id)},
        ATTR_MANUFACTURER: "Zengge",
        ATTR_MODEL: device.model,
        ATTR_NAME: entry.data.get(CONF_NAME, entry.title),
        ATTR_SW_VERSION: sw_version_str,
    }
    if hw_model := entry.data.get(CONF_MODEL):
        device_info[ATTR_HW_VERSION] = hw_model
    if entry.unique_id:
        device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    return device_info


class FluxBaseEntity(Entity):
    """Representation of a Flux entity without a coordinator."""

    _attr_should_poll = False

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the light."""
        self._device: AIOWifiLedBulb = device
        self.entry = entry
        self._attr_device_info = _async_device_info(self._device, entry)


class FluxEntity(CoordinatorEntity[FluxLedUpdateCoordinator]):
    """Representation of a Flux entity with a coordinator."""

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        base_unique_id: str,
        name: str,
        key: str | None,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device: AIOWifiLedBulb = coordinator.device
        self._responding = True
        self._attr_name = name
        if key:
            self._attr_unique_id = f"{base_unique_id}_{key}"
        else:
            self._attr_unique_id = base_unique_id
        self._attr_device_info = _async_device_info(self._device, coordinator.entry)

    async def _async_ensure_device_on(self) -> None:
        """Turn the device on if it needs to be turned on before a command."""
        if self._device.requires_turn_on and not self._device.is_on:
            await self._device.async_turn_on()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        return {"ip_address": self._device.ipaddr}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.last_update_success != self._responding:
            self.async_write_ha_state()
        self._responding = self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATE_UPDATED.format(self._device.ipaddr),
                self.async_write_ha_state,
            )
        )
        await super().async_added_to_hass()


class FluxOnOffEntity(FluxEntity):
    """Representation of a Flux entity that supports on/off."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified device on."""
        await self._async_turn_on(**kwargs)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @abstractmethod
    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified device on."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified device off."""
        await self._device.async_turn_off()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
