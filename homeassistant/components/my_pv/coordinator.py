"""Data update coordinator for the my-PV integration."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import functools
import logging
from typing import Any, Final, override

from my_pv import MyPVDevice
from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _my_pv_connection[T](
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> T:
        try:
            if not self.device.connected and not await self.device.connect():
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                )

            return await func(self, *args, **kwargs)
        except MyPVAuthenticationError as exc:
            raise ConfigEntryAuthFailed from exc
        except MyPVConnectionError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_unavailable",
                translation_placeholders={"uri": self.device.uri},
            ) from exc

    return wrapper


type MyPVConfigEntry = ConfigEntry[MyPVCoordinator]


class MyPVCoordinator(DataUpdateCoordinator[None]):
    """my-PV Data Update Coordinator."""

    config_entry: MyPVConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MyPVConfigEntry,
        device: MyPVDevice,
    ) -> None:
        """Initialize my-PV Data Update Coordinator."""
        assert device.serial_number
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=5),
            always_update=True,
        )

        self.device: Final[MyPVDevice] = device

        identifiers = {
            (DOMAIN, device.serial_number),
        }
        connections = set()

        if device.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, device.mac_address))

        name = f"my-PV {device.model}"

        self.device_info: Final[DeviceInfo] = DeviceInfo(
            configuration_url=device.setup_uri,
            connections=connections,
            identifiers=identifiers,
            manufacturer="my-PV",
            model=device.model,
            name=name,
            serial_number=device.serial_number,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )

    async def async_disconnect(self) -> bool:
        """Disconnect from my-PV.

        To be called when coordinator is unloaded, e.g. when device is removed or HA is shut down.
        """
        return await self.device.disconnect()

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            if not self.device.connected and not await self.device.connect():
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                )

            await self.device.fetch_data()
        except MyPVAuthenticationError as exc:
            raise ConfigEntryAuthFailed from exc
        except MyPVConnectionError as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_unavailable",
                translation_placeholders={"uri": self.device.uri},
            ) from exc

    @_my_pv_connection
    async def set_target_temperature(self, temperature: float) -> bool:
        """Set target temperature."""
        result = await self.device.set_target_temperature(temperature)
        self.async_update_listeners()
        return result

    def get_data_value(self, key: str) -> bool | float | int | str | None:
        """Get the data value for the given key."""
        return self.device.get_data_value(key)

    @_my_pv_connection
    async def turn_on(self) -> bool:
        """Turn on the device."""
        result = await self.device.turn_on()
        self.async_update_listeners()
        return result

    @_my_pv_connection
    async def turn_off(self) -> bool:
        """Turn off the device."""
        result = await self.device.turn_off()
        self.async_update_listeners()
        return result
