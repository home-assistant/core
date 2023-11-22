"""Acaia Scale Client for Home Assistant."""
from collections.abc import Awaitable, Callable
import logging
import time

from bleak import BleakGATTCharacteristic
from pyacaia_async import AcaiaScale
from pyacaia_async.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback as callback_decorator

_LOGGER = logging.getLogger(__name__)


class AcaiaClient(AcaiaScale):
    """Client to interact with Acaia Scales."""

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        name: str,
        is_new_style_scale: bool = True,
        notify_callback: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the client."""
        self._last_action_timestamp: float | None = None
        self.hass: HomeAssistant = hass
        self._name: str = name
        self._device_available: bool = False

        super().__init__(
            mac=mac,
            is_new_style_scale=is_new_style_scale,
            notify_callback=notify_callback,
        )

    @property
    def name(self) -> str:
        """Return the name of the scale."""
        return self._name

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

    async def async_update(self) -> None:
        """Update the data from the scale."""
        scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)
        if scanner_count == 0:
            self.connected = False
            _LOGGER.debug("Update coordinator: No bluetooth scanner available")
            return

        self._device_available = bluetooth.async_address_present(
            self.hass, self.mac, connectable=True
        )

        if not self.connected and self._device_available:
            _LOGGER.debug("Acaia Client: Connecting")
            await self.connect()

        elif not self._device_available:
            self.connected = False
            self.timer_running = False
            _LOGGER.debug(
                "Acaia Client: Device with MAC %s not available",
                self.mac,
            )
        else:
            # send auth to get the battery level and units
            await self.auth()
            await self.send_weight_notification_request()

    @callback_decorator
    async def tare(self) -> None:
        """Tare the scale."""
        await self.connect()
        await super().tare()

    async def start_stop_timer(self) -> None:
        """Start/Stop the timer."""
        await self.connect()
        await super().start_stop_timer()

    async def reset_timer(self) -> None:
        """Reset the timer."""
        await self.connect()
        await super().reset_timer()
