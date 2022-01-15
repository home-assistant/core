"""Base class for IKEA TRADFRI."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any, cast

from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.device.air_purifier import AirPurifier
from pytradfri.device.air_purifier_control import AirPurifierControl
from pytradfri.device.blind import Blind
from pytradfri.device.blind_control import BlindControl
from pytradfri.device.light import Light
from pytradfri.device.light_control import LightControl
from pytradfri.device.signal_repeater import SignalRepeater
from pytradfri.device.signal_repeater_control import SignalRepeaterControl
from pytradfri.device.socket import Socket
from pytradfri.device.socket_control import SocketControl
from pytradfri.error import PytradfriError

from homeassistant.const import Platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_CONTROLLER_NAME, ATTR_DEVICE_NAME, ATTR_SIGNAL_REPEATER, DOMAIN
from .coordinator import TradfriDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

MAP_DEVICE_CONTROL: dict = {
    Platform.LIGHT: {"device_name": "lights", "controller_name": "light_control"},
    Platform.COVER: {"device_name": "blinds", "controller_name": "blind_control"},
    Platform.FAN: {
        "device_name": "air_purifiers",
        "controller_name": "air_purifier_control",
    },
    ATTR_SIGNAL_REPEATER: {
        "device_name": "signal_repeaters",
        "controller_name": "signal_repeater_control",
    },
    Platform.SENSOR: {"device_name": None, "controller_name": None},
    Platform.SWITCH: {"device_name": "sockets", "controller_name": "socket_control"},
}


def _get_device_controller(
    device: Device,
    platform_type: str,
) -> BlindControl | LightControl | SocketControl | SignalRepeaterControl | AirPurifierControl | None:
    """Return the applicable device controller."""
    controller_name = MAP_DEVICE_CONTROL[platform_type][ATTR_CONTROLLER_NAME]

    try:
        return getattr(
            device,
            controller_name,
        )
    except (IndexError, AttributeError):
        return None


def _get_device_data(
    device_controller: BlindControl
    | LightControl
    | SocketControl
    | SignalRepeaterControl
    | AirPurifierControl
    | None,
    platform_name: str,
) -> Socket | Light | Blind | AirPurifier | SignalRepeater | None:
    """Return data from the controller data dictionary."""
    if not device_controller:
        return None

    try:
        return getattr(
            device_controller, MAP_DEVICE_CONTROL[platform_name][ATTR_DEVICE_NAME]
        )[0]
    except (IndexError, AttributeError):
        return None


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


class TradfriBaseDevice(CoordinatorEntity):
    """Base Tradfri device."""

    _platform_type: str

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        platform_type: str,
        gateway_id: str,
        api: Callable[[Command | list[Command]], Any],
    ) -> None:
        """Initialize a device."""
        super().__init__(device_coordinator)

        self._platform_type = platform_type

        self._gateway_id = gateway_id

        self._device: Device = device_coordinator.data
        self._attr_available = self._device.reachable

        self._coordinator = device_coordinator
        self._device_id = self._device.id
        self._api = handle_error(api)
        self._attr_name = self._device.name

        self._attr_unique_id = f"{self._gateway_id}-{self._device.id}"

    @property
    def _device_control(
        self,
    ) -> BlindControl | LightControl | SocketControl | SignalRepeaterControl | AirPurifierControl | None:
        """Return a device controller, if available."""
        if not self._platform_type:
            return None

        return _get_device_controller(
            device=self._device, platform_type=self._platform_type
        )

    @property
    def _device_data(
        self,
    ) -> Blind | Light | Socket | SignalRepeater | AirPurifier | None:
        """Get device data from the coordinator."""
        self._attr_available = self._device.reachable

        return _get_device_data(
            device_controller=self._device_control,
            platform_name=self._platform_type,
        )

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return cast(bool, self._device.reachable)
