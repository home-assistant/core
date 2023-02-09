"""Base entity for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

import async_timeout
from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, SENSIBO_ERRORS, TIMEOUT
from .coordinator import SensiboDataUpdateCoordinator

_T = TypeVar("_T", bound="SensiboDeviceBaseEntity")
_P = ParamSpec("_P")


def async_handle_api_call(
    function: Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]]:
    """Decorate api calls."""

    async def wrap_api_call(*args: Any, **kwargs: Any) -> None:
        """Wrap services for api calls."""
        res: bool = False
        try:
            async with async_timeout.timeout(TIMEOUT):
                res = await function(*args, **kwargs)
        except SENSIBO_ERRORS as err:
            raise HomeAssistantError from err

        LOGGER.debug("Result %s for entity %s with arguments %s", res, args[0], kwargs)
        entity: SensiboDeviceBaseEntity = args[0]
        if res is not True:
            raise HomeAssistantError(f"Could not execute service for {entity.name}")
        if kwargs.get("key") is not None and kwargs.get("value") is not None:
            setattr(entity.device_data, kwargs["key"], kwargs["value"])
            LOGGER.debug("Debug check key %s is now %s", kwargs["key"], kwargs["value"])
            entity.async_write_ha_state()
            await entity.coordinator.async_request_refresh()

    return wrap_api_call


class SensiboBaseEntity(CoordinatorEntity[SensiboDataUpdateCoordinator]):
    """Representation of a Sensibo Base Entity."""

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
    """Representation of a Sensibo Device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Sensibo Device."""
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


class SensiboMotionBaseEntity(SensiboBaseEntity):
    """Representation of a Sensibo Motion Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator, device_id)
        self._sensor_id = sensor_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            name=f"{self.device_data.name} Motion Sensor",
            via_device=(DOMAIN, device_id),
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=sensor_data.model,
            sw_version=sensor_data.fw_ver,
            hw_version=sensor_data.fw_type,
        )

    @property
    def sensor_data(self) -> MotionSensor | None:
        """Return data for Motion Sensor."""
        if TYPE_CHECKING:
            assert self.device_data.motion_sensors
        return self.device_data.motion_sensors[self._sensor_id]
