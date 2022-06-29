"""Base entity for Sensibo integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import async_timeout
from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, SENSIBO_ERRORS, TIMEOUT
from .coordinator import SensiboDataUpdateCoordinator


class SensiboBaseEntity(CoordinatorEntity[SensiboDataUpdateCoordinator]):
    """Representation of a Sensibo entity."""

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._client = coordinator.client

    @property
    def device_data(self) -> SensiboDevice:
        """Return data for device."""
        return self.coordinator.data.parsed[self._device_id]


class SensiboDeviceBaseEntity(SensiboBaseEntity):
    """Representation of a Sensibo device."""

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator, device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_data.id)},
            name=self.device_data.name,
            connections={(CONNECTION_NETWORK_MAC, self.device_data.mac)},
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=self.device_data.model,
            sw_version=self.device_data.fw_ver,
            hw_version=self.device_data.fw_type,
            suggested_area=self.device_data.name,
        )

    async def async_send_command(
        self, command: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send command to Sensibo api."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                result = await self.async_send_api_call(command, params)
        except SENSIBO_ERRORS as err:
            raise HomeAssistantError(
                f"Failed to send command {command} for device {self.name} to Sensibo servers: {err}"
            ) from err

        LOGGER.debug("Result: %s", result)
        return result

    async def async_send_api_call(
        self, command: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send api call."""
        result: dict[str, Any] = {"status": None}
        if command == "set_calibration":
            if TYPE_CHECKING:
                assert params is not None
            result = await self._client.async_set_calibration(
                self._device_id,
                params["data"],
            )
        if command == "set_ac_state":
            if TYPE_CHECKING:
                assert params is not None
            result = await self._client.async_set_ac_state_property(
                self._device_id,
                params["name"],
                params["value"],
                params["ac_states"],
                params["assumed_state"],
            )
        if command == "set_timer":
            if TYPE_CHECKING:
                assert params is not None
            result = await self._client.async_set_timer(self._device_id, params)
        if command == "del_timer":
            result = await self._client.async_del_timer(self._device_id)
        if command == "set_pure_boost":
            if TYPE_CHECKING:
                assert params is not None
            result = await self._client.async_set_pureboost(
                self._device_id,
                params,
            )
        if command == "reset_filter":
            result = await self._client.async_reset_filter(self._device_id)
        return result


class SensiboMotionBaseEntity(SensiboBaseEntity):
    """Representation of a Sensibo motion entity."""

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
        name: str | None,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator, device_id)
        self._sensor_id = sensor_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            name=f"{self.device_data.name} Motion Sensor {name}",
            via_device=(DOMAIN, device_id),
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=sensor_data.model,
            sw_version=sensor_data.fw_ver,
            hw_version=sensor_data.fw_type,
        )

    @property
    def sensor_data(self) -> MotionSensor | None:
        """Return data for device."""
        if TYPE_CHECKING:
            assert self.device_data.motion_sensors
        return self.device_data.motion_sensors[self._sensor_id]
