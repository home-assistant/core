"""Acaia Scale Client for Home Assistant."""
from collections.abc import Awaitable, Callable
import logging
import time

from bleak import BleakGATTCharacteristic
from pyacaia_async import AcaiaScale
from pyacaia_async.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class AcaiaClient(AcaiaScale):
    """Client to interact with Acaia Scales."""

    def __init__(
        self, hass: HomeAssistant, mac: str, name: str, is_new_style_scale: bool = True
    ) -> None:
        """Initialize the client."""
        self._last_action_timestamp: float | None = None
        self.hass: HomeAssistant = hass
        self._name: str = name
        super().__init__(mac=mac, is_new_style_scale=is_new_style_scale)

    @property
    def mac(self) -> str:
        """Return the mac address of the scale in upper case."""
        assert self._mac
        return self._mac.upper()

    @property
    def name(self) -> str:
        """Return the name of the scale."""
        return self._name

    @property
    def timer_running(self) -> bool:
        """Return whether the timer is running."""
        return self._timer_running

    @timer_running.setter
    def timer_running(self, value: bool) -> None:
        """Set timer running state."""
        self._timer_running = value

    @property
    def connected(self) -> bool:
        """Return whether the scale is connected."""
        return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connected state."""
        self._connected = value

    async def connect(
        self,
        callback: Callable[[BleakGATTCharacteristic, bytearray], Awaitable[None] | None]
        | None = None,
    ) -> None:
        """Connect to the scale."""
        try:
            if not self._connected:
                # Get a new client and connect to the scale.
                assert self._mac
                ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, self._mac, connectable=True
                )
                if ble_device is None:
                    raise AcaiaDeviceNotFound(f"Device with MAC {self._mac} not found")
                self.new_client_from_ble_device(ble_device)

                await super().connect(callback=callback)
                interval = 1 if self._is_new_style_scale else 5
                self.hass.async_create_task(
                    self._send_heartbeats(
                        interval=interval, new_style_heartbeat=self._is_new_style_scale
                    )
                )
                self.hass.async_create_task(self._process_queue())

            self._last_action_timestamp = time.time()
        except (AcaiaDeviceNotFound, AcaiaError) as ex:
            _LOGGER.warning(
                "Couldn't connect to device %s with MAC %s", self.name, self.mac
            )
            _LOGGER.debug("Full error: %s", str(ex))

    async def tare(self) -> None:
        """Tare the scale."""
        await self.connect()
        try:
            await super().tare()
        except Exception as ex:
            raise HomeAssistantError("Error taring device") from ex

    async def start_stop_timer(self) -> None:
        """Start/Stop the timer."""
        await self.connect()
        try:
            await super().start_stop_timer()
        except Exception as ex:
            raise HomeAssistantError("Error starting/stopping timer") from ex

    async def reset_timer(self) -> None:
        """Reset the timer."""
        await self.connect()
        try:
            await super().reset_timer()
        except Exception as ex:
            raise HomeAssistantError("Error resetting timer") from ex
