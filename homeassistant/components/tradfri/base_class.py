"""Base class for IKEA TRADFRI."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, cast

from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.error import RequestError

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import TradfriDeviceDataUpdateCoordinator


def handle_error(
    func: Callable[[Command | list[Command]], Any]
) -> Callable[[Command | list[Command]], Coroutine[Any, Any, None]]:
    """Handle tradfri api call error."""

    @wraps(func)
    async def wrapper(command: Command | list[Command]) -> None:
        """Decorate api call."""
        try:
            await func(command)
        except RequestError as err:
            LOGGER.error("Unable to execute command %s: %s", command, err)

    return wrapper


class TradfriBaseEntity(CoordinatorEntity[TradfriDeviceDataUpdateCoordinator]):
    """Base Tradfri device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        gateway_id: str,
        api: Callable[[Command | list[Command]], Any],
    ) -> None:
        """Initialize a device."""
        super().__init__(device_coordinator)

        self._gateway_id = gateway_id

        self._device: Device = device_coordinator.data

        self._device_id = self._device.id
        self._api = handle_error(api)

        self._attr_unique_id = f"{self._gateway_id}-{self._device.id}"

    @abstractmethod
    @callback
    def _refresh(self) -> None:
        """Refresh device data."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Tests fails without this method.
        """
        self._refresh()
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        info = self._device.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=info.manufacturer,
            model=info.model_number,
            name=self._device.name,
            sw_version=info.firmware_version,
            via_device=(DOMAIN, self._gateway_id),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return cast(bool, self._device.reachable) and super().available
