"""Base entity for Sensibo integration."""
from __future__ import annotations

from typing import Any

import async_timeout

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, SENSIBO_ERRORS, TIMEOUT
from .coordinator import SensiboDataUpdateCoordinator


class SensiboBaseEntity(CoordinatorEntity):
    """Representation of a Sensibo numbers."""

    coordinator: SensiboDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._client = coordinator.client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[device_id]["id"])},
            name=coordinator.data[device_id]["name"],
            connections={(CONNECTION_NETWORK_MAC, coordinator.data[device_id]["mac"])},
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=coordinator.data[device_id]["model"],
            sw_version=coordinator.data[device_id]["fw_ver"],
            hw_version=coordinator.data[device_id]["fw_type"],
            suggested_area=coordinator.data[device_id]["name"],
        )

    async def async_send_command(
        self, command: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send command to Sensibo api."""
        result: dict[str, Any] = {"status": None}
        if command == "set_calibration":
            try:
                async with async_timeout.timeout(TIMEOUT):
                    result = await self._client.async_set_calibration(
                        self._device_id,
                        params["value"],
                    )
            except SENSIBO_ERRORS as err:
                raise HomeAssistantError(
                    f"Failed to send command {command} for device {self.name} to Sensibo servers: {err}"
                ) from err
        if command == "set_ac_state":
            try:
                async with async_timeout.timeout(TIMEOUT):
                    result = await self._client.async_set_ac_state_property(
                        self._device_id,
                        params["name"],
                        params["value"],
                        params["ac_states"],
                        params["assumed_state"],
                    )
            except SENSIBO_ERRORS as err:
                raise HomeAssistantError(
                    f"Failed to send command {command} for device {self.name} to Sensibo servers: {err}"
                ) from err

        LOGGER.debug("Result: %s", result)
        return result
