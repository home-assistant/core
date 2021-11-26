"""Support for FluxLED/MagicHome lights."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any, cast

from flux_led.aiodevice import AIOWifiLedBulb

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FluxLedUpdateCoordinator
from .const import SIGNAL_STATE_UPDATED


class FluxEntity(CoordinatorEntity):
    """Representation of a Flux entity."""

    coordinator: FluxLedUpdateCoordinator

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device: AIOWifiLedBulb = coordinator.device
        self._responding = True
        self._attr_name = name
        self._attr_unique_id = unique_id
        if self.unique_id:
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, self.unique_id)},
                manufacturer="FluxLED/Magic Home",
                model=self._device.model,
                name=self.name,
                sw_version=str(self._device.version_num),
            )

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
        return cast(bool, self._device.is_on)

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
