"""An abstract class common to all Imou entities."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, override

from pyimouapi.const import PARAM_STATE, PARAM_STATUS
from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, imou_device_identifier
from .coordinator import ImouDataUpdateCoordinator


class ImouEntity(CoordinatorEntity[ImouDataUpdateCoordinator]):
    """Base class for all Imou entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        description: EntityDescription,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entity_type = description.key
        self._device_key = imou_device_identifier(device)
        self._attr_unique_id = f"{self._device_key}${description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_key)},
            name=device.channel_name or device.device_name,
            manufacturer=device.manufacturer,
            model=device.model,
            sw_version=device.swversion,
            serial_number=device.device_id,
        )

    @property
    def device(self) -> ImouHaDevice:
        """Return the live device from the coordinator.

        Callers must guard with `available` first; accessing this for a device
        that has left the account raises `KeyError`.
        """
        return self.coordinator.devices_by_key[self._device_key]

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        if (
            not super().available
            or self._device_key not in self.coordinator.devices_by_key
        ):
            return False
        if self._entity_type == PARAM_STATUS:
            return True
        if PARAM_STATUS not in self.device.sensors:
            return False
        return (
            self.device.sensors[PARAM_STATUS][PARAM_STATE] != DeviceStatus.OFFLINE.value
        )


def async_wrap_imou_command[_T: ImouEntity, **_P, _R](
    error_key: str,
) -> Callable[
    [Callable[Concatenate[_T, _P], Awaitable[_R]]],
    Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]],
]:
    """Wrap an Imou command and start reauthentication when credentials are rejected."""

    def decorator(
        func: Callable[Concatenate[_T, _P], Awaitable[_R]],
    ) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]:
        @wraps(func)
        async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
            try:
                return await func(self, *args, **kwargs)
            except InvalidAppIdOrSecretException as err:
                self.coordinator.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                ) from err
            except ImouException as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=error_key,
                    translation_placeholders={"error": err.message},
                ) from err

        return wrapper

    return decorator
