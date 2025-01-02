"""Base entity for Sensibo integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate

from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, SENSIBO_ERRORS, TIMEOUT
from .coordinator import SensiboDataUpdateCoordinator


def async_handle_api_call[_T: SensiboDeviceBaseEntity, **_P](
    function: Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]]:
    """Decorate api calls."""

    async def wrap_api_call(entity: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap services for api calls."""
        res: bool = False
        if TYPE_CHECKING:
            assert isinstance(entity.name, str)
        try:
            async with asyncio.timeout(TIMEOUT):
                res = await function(entity, *args, **kwargs)
        except SENSIBO_ERRORS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_raised",
                translation_placeholders={"error": str(err), "name": entity.name},
            ) from err

        LOGGER.debug("Result %s for entity %s with arguments %s", res, entity, kwargs)
        if res is not True:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_result_not_true",
                translation_placeholders={"name": entity.name},
            )
        if (
            isinstance(key := kwargs.get("key"), str)
            and (value := kwargs.get("value")) is not None
        ):
            setattr(entity.device_data, key, value)
            LOGGER.debug("Debug check key %s is now %s", key, value)
            entity.async_write_ha_state()
            await entity.coordinator.async_request_refresh()

    return wrap_api_call


class SensiboBaseEntity(CoordinatorEntity[SensiboDataUpdateCoordinator]):
    """Representation of a Sensibo Base Entity."""

    _attr_has_entity_name = True

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device_data.available and super().available


class SensiboDeviceBaseEntity(SensiboBaseEntity):
    """Representation of a Sensibo Device."""

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
            serial_number=self.device_data.serial,
        )


class SensiboMotionBaseEntity(SensiboBaseEntity):
    """Representation of a Sensibo Motion Entity."""

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
    def sensor_data(self) -> MotionSensor:
        """Return data for Motion Sensor."""
        if TYPE_CHECKING:
            assert self.device_data.motion_sensors
        return self.device_data.motion_sensors[self._sensor_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.sensor_data.alive) and super().available
