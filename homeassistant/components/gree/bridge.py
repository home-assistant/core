"""Helper and wrapper classes for Gree module."""
from datetime import timedelta
import logging
from typing import List

from greeclimate.device import Device, DeviceInfo
from greeclimate.discovery import Discovery
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError

from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_ERRORS

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    def __init__(self, hass: HomeAssistant, device: Device):
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.device_info.name}",
            update_interval=timedelta(seconds=60),
        )
        self._device = device
        self._error_count = 0

    async def _async_update_data(self):
        """Update the state of the device."""
        try:
            await self._device.update_state()

            if not self.last_update_success and self._error_count:
                _LOGGER.warning(
                    "Device is available: %s (%s)",
                    self.name,
                    str(self._device.device_info),
                )

            self._error_count = 0
        except DeviceTimeoutError as error:
            self._error_count += 1

            # Under normal conditions GREE units timeout every once in a while
            if self.last_update_success and self._error_count >= MAX_ERRORS:
                _LOGGER.warning(
                    "Device is unavailable: %s (%s)",
                    self.name,
                    self._device.device_info,
                )
                raise UpdateFailed(error) from error

    async def push_state_update(self):
        """Send state updates to the physical device."""
        try:
            return await self._device.push_state_update()
        except DeviceTimeoutError:
            _LOGGER.warning(
                "Timeout send state update to: %s (%s)",
                self.name,
                self._device.device_info,
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown exception caught while sending state update to: %s (%s)",
                self.name,
                self._device.device_info,
            )

    @property
    def device_info(self):
        """Return the gree device information."""
        return self._device.device_info

    @property
    def light(self) -> bool:
        """Return if the front panel light is on."""
        return self._device.light

    @light.setter
    def light(self, value: bool):
        """Set the front panel light on/off."""
        self._device.light = value

    @property
    def temperature_units(self) -> int:
        """Return the temperature units for the device."""
        return self._device.temperature_units

    @property
    def target_temperature(self) -> int:
        """Return the target temperature for the device."""
        return self._device.target_temperature

    @target_temperature.setter
    def target_temperature(self, value: int):
        """Set the target temperature for the device."""
        self._device.target_temperature = value

    @property
    def power(self) -> bool:
        """Return the power state of the device."""
        return self._device.power

    @power.setter
    def power(self, value: bool):
        """Set the power state of the device."""
        self._device.power = value

    @property
    def mode(self) -> int:
        """Get the current mode of the device."""
        return self._device.mode

    @mode.setter
    def mode(self, value: int):
        """Set the HVAC mode of the device."""
        self._device.mode = value

    @property
    def fan_speed(self) -> int:
        """Get the fan speed of the device."""
        return self._device.fan_speed

    @fan_speed.setter
    def fan_speed(self, value: int):
        """Set the fan speed of the device."""
        self._device.fan_speed = value

    @property
    def sleep(self) -> bool:
        """Get sleep mode enabled on the device."""
        return self._device.sleep

    @sleep.setter
    def sleep(self, value: bool):
        """Set sleep mode enabled/disabled on the device."""
        self._device.sleep = value

    @property
    def horizontal_swing(self) -> int:
        """Get the horizontal swing mode on the device."""
        return self._device.horizontal_swing

    @horizontal_swing.setter
    def horizontal_swing(self, value: int):
        """Set the horizontal swing mode on the device."""
        self._device.horizontal_swing = value

    @property
    def vertical_swing(self) -> int:
        """Get the vertical swing mode on the device."""
        return self._device.vertical_swing

    @vertical_swing.setter
    def vertical_swing(self, value: int):
        """Set the vertical swing mode on the device."""
        self._device.vertical_swing = value

    @property
    def turbo(self) -> bool:
        """Get turbo mode enabled on the device."""
        return self._device.turbo

    @turbo.setter
    def turbo(self, value: bool):
        """Set turbo mode enabled/disabled on the device."""
        self._device.turbo = value

    @property
    def steady_heat(self) -> bool:
        """Get steady heat enabled on the device."""
        return self._device.steady_heat

    @steady_heat.setter
    def steady_heat(self, value: bool):
        """Set steady heat mode enabled/disabled on the device."""
        self._device.steady_heat = value

    @property
    def power_save(self) -> bool:
        """Get power saving mode enabled on the device."""
        return self._device.power_save

    @power_save.setter
    def power_save(self, value: bool):
        """Set power saving mode enabled/disabled on the device."""
        self._device.power_save = value


class DeviceHelper:
    """Device search and bind wrapper for Gree platform."""

    @staticmethod
    async def try_bind_device(device_info: DeviceInfo) -> Device:
        """Try and bing with a discovered device.

        Note the you must bind with the device very quickly after it is discovered, or the
        process may not be completed correctly, raising a `CannotConnect` error.
        """
        device = Device(device_info)
        try:
            await device.bind()
        except DeviceNotBoundError as exception:
            raise CannotConnect from exception
        return device

    @staticmethod
    async def find_devices() -> List[DeviceInfo]:
        """Gather a list of device infos from the local network."""
        return await Discovery.search_devices()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
