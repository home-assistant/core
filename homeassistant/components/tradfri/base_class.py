"""Base class for IKEA TRADFRI."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any

from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.device.air_purifier import AirPurifier
from pytradfri.device.air_purifier_control import AirPurifierControl
from pytradfri.device.blind import Blind
from pytradfri.device.blind_control import BlindControl
from pytradfri.device.light import Light
from pytradfri.device.light_control import LightControl
from pytradfri.device.signal_repeater_control import SignalRepeaterControl
from pytradfri.device.socket import Socket
from pytradfri.device.socket_control import SocketControl
from pytradfri.error import PytradfriError

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, SIGNAL_GW

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
        self._attr_name = device.name
        self._device: Device = device
        self._device_control: BlindControl | LightControl | SocketControl | SignalRepeaterControl | AirPurifierControl | None = (
            None
        )
        self._device_data: Socket | Light | Blind | AirPurifier | None = None
        self._gateway_id = gateway_id

    async def _async_run_observe(self, cmd: Command) -> None:
        """Run observe in a coroutine."""
        try:
            await self._api(cmd)
        except PytradfriError as err:
            self._attr_available = False
            self.async_write_ha_state()
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    @callback
    def _async_start_observe(self, exc: Exception | None = None) -> None:
        """Start observation of device."""
        if exc:
            self._attr_available = False
            self.async_write_ha_state()
            _LOGGER.warning("Observation failed for %s", self._attr_name, exc_info=exc)
        cmd = self._device.observe(
            callback=self._observe_update,
            err_callback=self._async_start_observe,
            duration=0,
        )
        self.hass.async_create_task(self._async_run_observe(cmd))

    async def async_added_to_hass(self) -> None:
        """Start thread when added to hass."""
        self._async_start_observe()

    @callback
    def _observe_update(self, device: Device) -> None:
        """Receive new state data for this device."""
        self._refresh(device)

    def _refresh(self, device: Device, write_ha: bool = True) -> None:
        """Refresh the device data."""
        self._device = device
        self._attr_name = device.name
        if write_ha:
            self.async_write_ha_state()


class TradfriBaseDevice(TradfriBaseClass):
    """Base class for a TRADFRI device.

    All devices should inherit from this class.
    """

    def __init__(
        self,
        device: Device,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a device."""
        self._attr_available = device.reachable
        self._hub_available = True
        super().__init__(device, api, gateway_id)

    async def async_added_to_hass(self) -> None:
        """Start thread when added to hass."""
        # Only devices shall receive SIGNAL_GW
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_GW, self.set_hub_available)
        )
        await super().async_added_to_hass()

    @callback
    def set_hub_available(self, available: bool) -> None:
        """Set status of hub."""
        if available != self._hub_available:
            self._hub_available = available
            self._refresh(self._device)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        info = self._device.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=info.manufacturer,
            model=info.model_number,
            name=self._attr_name,
            sw_version=info.firmware_version,
            via_device=(DOMAIN, self._gateway_id),
        )

    def _refresh(self, device: Device, write_ha: bool = True) -> None:
        """Refresh the device data."""
        # The base class _refresh cannot be used, because
        # there are devices (group) that do not have .reachable
        # so set _attr_available here and let the base class do the rest.
        self._attr_available = device.reachable and self._hub_available
        super()._refresh(device, write_ha)
