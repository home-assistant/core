"""Base class for IKEA TRADFRI."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any

from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.device.blind import Blind
from pytradfri.device.blind_control import BlindControl
from pytradfri.device.light import Light
from pytradfri.device.light_control import LightControl
from pytradfri.device.signal_repeater_control import SignalRepeaterControl
from pytradfri.device.socket import Socket
from pytradfri.device.socket_control import SocketControl
from pytradfri.error import PytradfriError

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def handle_error(
    func: Callable[[Command | list[Command]], Any]
) -> Callable[[str], Any]:
    """Handle tradfri api call error."""

    @wraps(func)
    async def wrapper(command: Command | list[Command]) -> None:
        """Decorate api call."""
        try:
            await func(command)
        except PytradfriError as err:
            _LOGGER.error("Unable to execute command %s: %s", command, err)

    return wrapper


class TradfriBaseClass(Entity):
    """Base class for IKEA TRADFRI.

    All devices and groups should ultimately inherit from this class.
    """

    _attr_should_poll = False

    def __init__(
        self,
        device: Device,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a device."""
        self._api = handle_error(api)
        self._device: Device = device
        self._device_control: BlindControl | LightControl | SocketControl | SignalRepeaterControl | None = (
            None
        )
        self._device_data: Socket | Light | Blind | None = None
        self._gateway_id = gateway_id
        self._refresh(device)

    @callback
    def _async_start_observe(self, exc: Exception | None = None) -> None:
        """Start observation of device."""
        if exc:
            self.async_write_ha_state()
            _LOGGER.warning("Observation failed for %s", self._attr_name, exc_info=exc)

        try:
            cmd = self._device.observe(
                callback=self._observe_update,
                err_callback=self._async_start_observe,
                duration=0,
            )
            self.hass.async_create_task(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    async def async_added_to_hass(self) -> None:
        """Start thread when added to hass."""
        self._async_start_observe()

    @callback
    def _observe_update(self, device: Device) -> None:
        """Receive new state data for this device."""
        self._refresh(device)
        self.async_write_ha_state()

    def _refresh(self, device: Device) -> None:
        """Refresh the device data."""
        self._device = device
        self._attr_name = device.name


class TradfriBaseDevice(TradfriBaseClass):
    """Base class for a TRADFRI device.

    All devices should inherit from this class.
    """

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        info = self._device.device_info
        return {
            "identifiers": {(DOMAIN, self._device.id)},
            "manufacturer": info.manufacturer,
            "model": info.model_number,
            "name": self._attr_name,
            "sw_version": info.firmware_version,
            "via_device": (DOMAIN, self._gateway_id),
        }

    def _refresh(self, device: Device) -> None:
        """Refresh the device data."""
        super()._refresh(device)
        self._attr_available = device.reachable
