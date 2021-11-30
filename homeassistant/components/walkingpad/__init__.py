"""Support for Xiaomi WalkingPad treadmill."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from bleak.exc import BleakError
from miio.exceptions import DeviceException
from miio.walkingpad import OperationMode, Walkingpad, WalkingpadStatus
from ph4_walkingpad.pad import Controller, WalkingPad

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    AWAIT_SLEEP_INTERVAL,
    CONF_CONN_TYPE,
    CONF_DEFAULT_SPEED,
    CONF_UUID,
    DEFAULT_SPEED,
    DOMAIN,
    MAX_SPEED,
    MIN_SPEED,
    MODES_DICT,
)

PARALLEL_UPDATES: Final = 1

PLATFORMS: Final = ["remote"]

_LOGGER = logging.getLogger(__name__)

# turn off ph4-walkingpad logger
logging.getLogger("ph4_walkingpad.pad").setLevel(logging.CRITICAL)
logging.getLogger("ph4_walkingpad").setLevel(logging.CRITICAL)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WalkingPad device from a config entry."""
    device = (
        WalkingPadBLEDevice(hass, entry)
        if entry.data[CONF_CONN_TYPE] == "ble"
        else WalkingPadWiFiDevice(hass, entry)
    )

    await device.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        device._default_speed = entry.options.get(CONF_DEFAULT_SPEED, DEFAULT_SPEED)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


class WalkingPadBaseDevice:
    """Base class for WalkingPad device."""

    min_speed = MIN_SPEED
    max_speed = MAX_SPEED

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize device."""
        self._hass = hass
        self._config = config
        self._name = "WalkingPad"
        self._default_speed = config.options.get(CONF_DEFAULT_SPEED, DEFAULT_SPEED)
        self._speed_user = self._default_speed

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        return self._name

    @property
    def config(self) -> ConfigEntry:
        """Return device config."""
        return self._config

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        raise NotImplementedError

    async def set_speed_user(self, speed: float) -> None:
        """Set user speed."""
        self._speed_user = speed / 10

    async def set_mode_standby(self) -> None:
        """Set mode to standby."""
        raise NotImplementedError

    async def set_mode_manual(self) -> None:
        """Set mode to manual."""
        raise NotImplementedError

    async def set_mode_auto(self) -> None:
        """Set mode to auto."""
        raise NotImplementedError

    async def set_mode(self, mode: str) -> None:
        """Set mode."""
        if mode == "standby":
            await self.set_mode_standby()
        elif mode == "manual":
            await self.set_mode_manual()
        elif mode == "auto":
            await self.set_mode_auto()
        else:
            raise ValueError("Invalid mode")

    async def async_setup(self) -> None:
        """Set up device."""
        raise NotImplementedError


class WalkingPadBLEDevice(WalkingPadBaseDevice):
    """Represents single WalkingPad BLE device."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize device."""
        super().__init__(hass, config)
        self._uuid = config.data[CONF_UUID]
        self._walkingpad = Controller()
        self._walkingpad.log_messages_info = False
        self._available_device = False
        self._available_data = False

    @property
    def _mode(self) -> str:
        """Return device mode: standby, manual or auto."""
        return MODES_DICT[self.walkingpad.last_status.manual_mode]

    @property
    def _speed(self) -> Any:
        """Return device current speed in km/h."""
        return round(self.walkingpad.last_status.speed / 10, 2)

    @property
    def _steps(self) -> Any:
        """Return current number of steps."""
        return self.walkingpad.last_status.steps

    @property
    def _time(self) -> Any:
        """Return current walking time in seconds."""
        return self.walkingpad.last_status.time

    @property
    def _dist(self) -> Any:
        """Return current distance in kilometers."""
        return round(self.walkingpad.last_status.dist / 100, 2)

    @property
    def state(self) -> str:
        """Return true if device is available."""
        if self.mode in ["auto", "manual"]:
            state = STATE_ON
        else:
            state = STATE_OFF
        return state

    @property
    def mode(self) -> str | None:
        """Return device mode: standby, manual or auto."""
        return self._mode

    @property
    def speed(self) -> Any:
        """Return device current speed in km/h."""
        return self._speed

    @property
    def steps(self) -> Any:
        """Return current number of steps."""
        return self._steps

    @property
    def time(self) -> Any:
        """Return current walking time in seconds."""
        return self._time

    @property
    def dist(self) -> Any:
        """Return current distance in kilometers."""
        return self._dist

    @property
    def speed_user(self) -> Any:
        """Return speed set by user."""
        if self.speed == 0:
            speed = self._speed_user
        else:
            speed = self._speed
        return speed

    @property
    def default_speed(self) -> Any:
        """Return configured default speed."""
        return self._default_speed

    @property
    def walkingpad(self) -> WalkingPad:
        """Return WalkingPad instance."""
        return self._walkingpad

    @property
    def uuid(self) -> Any:
        """Return UUID."""
        return self._uuid

    @property
    def available_device(self) -> bool:
        """Return true if device is available."""
        return self._available_device

    @property
    def available_data(self) -> bool:
        """Return true if device data is available."""
        return self._available_data

    @property
    def available(self) -> bool:
        """Return true if device and its data are available."""
        return self.available_device & self.available_data

    async def _connect(self) -> None:
        """Connect to device."""
        await self._walkingpad.run(self.uuid)
        await asyncio.sleep(2.0)
        self._available_device = True
        await self._walkingpad.ask_stats()
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL)
        self._available_data = True
        _LOGGER.debug("%s: connected", self.name)

    async def connect(self) -> None:
        """Try to connect to device once."""
        try:
            await self._connect()
        except BleakError as exc:
            _LOGGER.error("%s: can't connect. %s", self.name, exc)

    async def connection_loop(self) -> None:
        """Try to connect to device until successful."""
        while not self.available_device:
            await asyncio.sleep(5.0)
            try:
                await self._connect()
            except BleakError as exc:
                _LOGGER.debug(
                    "%s: can't connect. %s. Retrying in 5 seconds", self.name, exc
                )

    async def check_if_available(self) -> None:
        """Check if device and its data are available."""
        try:
            self._available_device = bool(self.walkingpad.client.is_connected)
        except BleakError:
            self._available_device = False

        try:
            self._available_data = self.walkingpad.last_status is not None
        except BleakError:
            self._available_data = False

    async def set_speed(self, speed: float) -> None:
        """Change speed."""
        self._speed_user = speed / 10
        await self._walkingpad.change_speed(speed)
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL)

    async def start_belt(self) -> None:
        """Start belt."""
        await self._walkingpad.start_belt()
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL + 1.5)

    async def stop_belt(self) -> None:
        """Stop belt."""
        await self._walkingpad.stop_belt()
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL)

    async def set_mode_manual(self) -> None:
        """Set mode to manual."""
        await self._walkingpad.switch_mode(WalkingPad.MODE_MANUAL)
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL)

    async def set_mode_auto(self) -> None:
        """Set mode to auto."""
        await self._walkingpad.switch_mode(WalkingPad.MODE_AUTOMAT)
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL)

    async def set_mode_standby(self) -> None:
        """Set mode to standby."""
        await self._walkingpad.switch_mode(WalkingPad.MODE_STANDBY)
        await asyncio.sleep(AWAIT_SLEEP_INTERVAL)

    async def async_setup(self) -> None:
        """Set up device."""
        await self.connect()

    async def async_update(self) -> None:
        """Update device properties and send data updated signal."""
        await self.check_if_available()
        if self.available_device:
            await self._walkingpad.ask_stats()
            await asyncio.sleep(AWAIT_SLEEP_INTERVAL)
        else:
            _LOGGER.warning("%s is not connected. Trying to connect", self.name)
            await self.connection_loop()


class WalkingPadWiFiDevice(WalkingPadBaseDevice):
    """Represents single WalkingPad WiFi device."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize device."""
        super().__init__(hass, config)
        self._walkingpad_device = Walkingpad(
            config.data[CONF_IP_ADDRESS], config.data[CONF_TOKEN]
        )
        self._walkingpad_status = None
        self._available = False

    @property
    def walkingpad_device(self) -> Walkingpad:
        """Return walkingpad device."""
        return self._walkingpad_device

    @property
    def walkingpad_status(self) -> WalkingpadStatus:
        """Return walkingpad device."""
        return self._walkingpad_status

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        return self._available

    @property
    def _mode(self) -> str:
        """Return device mode: standby, manual or auto."""
        return MODES_DICT[self.walkingpad_status.mode.value]

    @property
    def _speed(self) -> Any:
        """Return device current speed in km/h."""
        return self.walkingpad_status.speed

    @property
    def _steps(self) -> Any:
        """Return current number of steps."""
        return self.walkingpad_status.step_count

    @property
    def _time(self) -> Any:
        """Return current walking time in seconds."""
        return self.walkingpad_status.walking_time.total_seconds()

    @property
    def _dist(self) -> float | Any:
        """Return current distance in meters."""
        return round(self.walkingpad_status.distance / 1000, 2)

    @property
    def state(self) -> str:
        """Return true if device is available."""
        if self.mode in ["auto", "manual"]:
            state = STATE_ON
        else:
            state = STATE_OFF
        return state

    @property
    def mode(self) -> Any:
        """Return device mode: standby, manual or auto."""
        return self._mode

    @property
    def speed(self) -> Any:
        """Return device current speed in km/h."""
        return self._speed

    @property
    def steps(self) -> Any:
        """Return current number of steps."""
        return self._steps

    @property
    def time(self) -> Any:
        """Return current walking time in seconds."""
        return self._time

    @property
    def dist(self) -> Any:
        """Return current distance in kilometers."""
        return self._dist

    @property
    def speed_user(self) -> Any:
        """Return speed set by user."""
        if self.speed == 0:
            speed = self._speed_user
        else:
            speed = self._speed
        return speed

    @property
    def default_speed(self) -> Any:
        """Return configured default speed."""
        return self._default_speed

    async def set_speed(self, speed: float) -> None:
        """Change speed."""
        self._speed_user = speed / 10
        await self._hass.async_add_executor_job(
            self._walkingpad_device.set_speed, speed / 10
        )

    async def start_belt(self) -> None:
        """Start belt."""
        await self._hass.async_add_executor_job(self._walkingpad_device.start)

    async def stop_belt(self) -> None:
        """Stop belt."""
        await self._hass.async_add_executor_job(self._walkingpad_device.stop)

    async def set_mode_manual(self) -> None:
        """Set mode to manual."""
        await self._hass.async_add_executor_job(
            self._walkingpad_device.set_mode, OperationMode(1)
        )

    async def set_mode_auto(self) -> None:
        """Set mode to auto."""
        await self._hass.async_add_executor_job(
            self._walkingpad_device.set_mode, OperationMode(0)
        )

    async def set_mode_standby(self) -> None:
        """Set mode to standby."""
        await self._hass.async_add_executor_job(
            self._walkingpad_device.set_mode, OperationMode(2)
        )

    async def async_setup(self) -> None:
        """Set up device."""
        try:
            self._walkingpad_status = await self._hass.async_add_executor_job(
                self.walkingpad_device.quick_status
            )
            self._available = True
        except DeviceException:
            self._available = False

    async def async_update(self) -> None:
        """Update device properties and send data updated signal."""
        try:
            self._walkingpad_status = await self._hass.async_add_executor_job(
                self.walkingpad_device.quick_status
            )
            self._available = True
        except DeviceException:
            if self._available:
                _LOGGER.warning("%s is not connected", self.name)
            self._available = False


class WalkingPadEntity(Entity):
    """Represents single WalkingPad entity."""

    def __init__(self, device: WalkingPadBLEDevice | WalkingPadWiFiDevice):
        """Initialize the entity."""
        self._device = device

    @property
    def device(self) -> WalkingPadBLEDevice | WalkingPadWiFiDevice:
        """Return device instance."""
        return self._device

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.device.config.entry_id)},
            "name": self.device.name,
            "manufacturer": "Xiaomi",
        }

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self.device.available
