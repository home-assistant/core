"""Support for IKEA Tradfri switches."""

from __future__ import annotations

from typing import Any, cast

from pytradfri.api.aiocoap_api import APIRequestProtocol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_GATEWAY_ID, DOMAIN
from .coordinator import TradfriDeviceDataUpdateCoordinator
from .entity import TradfriBaseEntity
from .models import TradfriData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Tradfri switches based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data: TradfriData = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data.api

    async_add_entities(
        TradfriSwitch(
            device_coordinator,
            api,
            gateway_id,
        )
        for device_coordinator in tradfri_data.coordinators
        if device_coordinator.device.has_socket_control
    )


class TradfriSwitch(TradfriBaseEntity, SwitchEntity):
    """The platform class required by Home Assistant."""

    _attr_name = None

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: APIRequestProtocol,
        gateway_id: str,
    ) -> None:
        """Initialize a switch."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self._device_control = self._device.socket_control
        self._device_data = self._device_control.sockets[0]

    def _refresh(self) -> None:
        """Refresh the device."""
        self._device_data = self.coordinator.data.socket_control.sockets[0]

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if not self._device_data:
            return False
        return cast(bool, self._device_data.state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_state(False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_state(True))
