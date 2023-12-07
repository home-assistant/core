"""Acaia Scale Client for Home Assistant."""
from collections.abc import Awaitable, Callable
import logging

from bleak import BleakGATTCharacteristic
from pyacaia_async import AcaiaScale
from pyacaia_async.const import HEARTBEAT_INTERVAL
from pyacaia_async.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import CONF_IS_NEW_STYLE_SCALE

_LOGGER = logging.getLogger(__name__)


class AcaiaClient(AcaiaScale):
    """Client to interact with Acaia Scales."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        notify_callback: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the client."""

        self.hass: HomeAssistant = hass
        self.entry: ConfigEntry = entry
        self._name: str = entry.data[CONF_NAME]

        super().__init__(
            mac=entry.data[CONF_MAC],
            is_new_style_scale=entry.data.get(CONF_IS_NEW_STYLE_SCALE, True),
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

        except (AcaiaDeviceNotFound, AcaiaError) as ex:
            _LOGGER.warning(
                "Couldn't connect to device %s with MAC %s", self.name, self.mac
            )
            _LOGGER.debug("Full error: %s", str(ex))

    def _setup_tasks(self) -> None:
        """Set up background tasks."""

        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = self.entry.async_create_background_task(
                hass=self.hass,
                target=self._send_heartbeats(
                    interval=HEARTBEAT_INTERVAL if not self._is_new_style_scale else 1,
                    new_style_heartbeat=self._is_new_style_scale,
                ),
                name="acaia_heartbeat_task",
            )
        if not self._process_queue_task or self._process_queue_task.done():
            self._process_queue_task = self.entry.async_create_background_task(
                hass=self.hass,
                target=self._process_queue(),
                name="acaia_process_queue_task",
            )

    async def async_update(self) -> None:
        """Update the data from the scale."""
        scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)
        if scanner_count == 0:
            self._connected = False
            _LOGGER.debug("Update coordinator: No bluetooth scanner available")
            return

        device_available = bluetooth.async_address_present(
            self.hass, self.mac, connectable=True
        )

        if device_available:
            await self.connect()
            # send auth to get the battery level and units
            await self.auth()
            await self.send_weight_notification_request()

        else:
            self._connected = False
            self._timer_running = False
            _LOGGER.debug(
                "Acaia Client: Device with MAC %s not available",
                self.mac,
            )
            if self._notify_callback:
                self._notify_callback()
