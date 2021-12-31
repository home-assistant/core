"""Support for IKEA Tradfri switches."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseDevice
from .const import CONF_GATEWAY_ID, DEVICES, DOMAIN, KEY_API


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Tradfri switches based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data[KEY_API]
    devices = tradfri_data[DEVICES]

    async_add_entities(
        TradfriSwitch(dev, api, gateway_id) for dev in devices if dev.has_socket_control
    )


class TradfriSwitch(TradfriBaseDevice, SwitchEntity):
    """The platform class required by Home Assistant."""

    def __init__(
        self,
        device: Command,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a switch."""
        super().__init__(device, api, gateway_id)
        self._attr_unique_id = f"{gateway_id}-{device.id}"

    def _refresh(self, device: Command, write_ha: bool = True) -> None:
        """Refresh the switch data."""
        # Caching of switch control and switch object
        self._device_control = device.socket_control
        self._device_data = device.socket_control.sockets[0]
        super()._refresh(device, write_ha=write_ha)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if not self._device_control:
            return None
        await self._api(self._device_control.set_state(False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        if not self._device_control:
            return None
        await self._api(self._device_control.set_state(True))
