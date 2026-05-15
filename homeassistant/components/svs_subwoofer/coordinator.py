"""DataUpdateCoordinator for SVS Subwoofer."""

import asyncio
import contextlib
import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import BleakNotFoundError, establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_DELAY,
    DOMAIN,
    EVENT_SVS_SUBWOOFER,
    SVS_CHAR_UUID,
    SYNCABLE_PARAMS,
    TRIGGER_SUBTYPE_DEFAULT,
    TRIGGER_TYPE_CONNECTED,
    TRIGGER_TYPE_DISCONNECTED,
    TRIGGER_TYPE_PRESET_LOADED,
)
from .svs_protocol import FrameAssembler, svs_encode

_LOGGER = logging.getLogger(__name__)

MAX_CONNECT_RETRIES = 3


class SVSSubwooferCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for SVS Subwoofer BLE communication."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
        name: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"SVS Subwoofer {name}",
        )
        self.address = address
        self.device_name = name
        self._client: BleakClient | None = None
        self._frame_assembler = FrameAssembler()
        self._connected = False
        self._command_lock = asyncio.Lock()
        self._disconnect_lock = asyncio.Lock()
        self.data: dict[str, Any] = {}
        self._device_id: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the subwoofer."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            name=self.device_name,
            manufacturer="SVS",
            model="Subwoofer",
        )

    @property
    def is_connected(self) -> bool:
        """Return True if connected to the subwoofer."""
        return self._connected

    def _get_device_id(self) -> str | None:
        """Get the device ID from the device registry, cached."""
        if self._device_id is not None:
            return self._device_id
        device = dr.async_get(self.hass).async_get_device(
            identifiers={(DOMAIN, self.address)}
        )
        if device is not None:
            self._device_id = device.id
        return self._device_id

    def _fire_event(self, trigger_type: str, subtype: str | None = None) -> None:
        """Fire a device automation event."""
        device_id = self._get_device_id()
        if not device_id:
            return
        event_data: dict[str, str] = {
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        if subtype:
            event_data["subtype"] = subtype
        self.hass.bus.async_fire(EVENT_SVS_SUBWOOFER, event_data)

    async def _async_setup(self) -> None:
        """Connect and request initial state."""
        await self._connect()
        await self._request_full_settings()

    async def _async_update_data(self) -> dict[str, Any]:
        """Push-based; reconnect if needed and return current snapshot."""
        if not self._connected:  # pragma: no cover - update_interval not set
            await self._connect()
            await self._request_full_settings()
        return self.data

    async def _connect(self) -> None:
        """Establish BLE connection with notifications."""
        if self._connected and self._client and self._client.is_connected:
            return

        ble_device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Device {self.address} not found. "
                "Check the subwoofer is powered on and the SVS app is disconnected."
            )

        try:
            self._client = await establish_connection(
                BleakClient,
                ble_device,
                self.address,
                disconnected_callback=self._on_disconnect,
                max_attempts=MAX_CONNECT_RETRIES,
            )
            await self._client.start_notify(SVS_CHAR_UUID, self._notification_handler)
        except BleakNotFoundError as err:
            raise UpdateFailed(f"Device {self.address} not found: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed(f"Timeout connecting to {self.address}: {err}") from err
        except BleakError as err:
            raise UpdateFailed(f"Failed to connect to {self.address}: {err}") from err

        self._connected = True
        self.async_set_updated_data(self.data)
        self._fire_event(TRIGGER_TYPE_CONNECTED)

    @callback
    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection from device."""
        self._connected = False
        self._frame_assembler.reset()
        self.async_set_updated_data(self.data)
        self._fire_event(TRIGGER_TYPE_DISCONNECTED)

    @callback
    def _notification_handler(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle incoming BLE notifications."""
        decoded = self._frame_assembler.add_data(bytes(data))
        if not decoded or not decoded.get("FRAME_RECOGNIZED"):
            return
        validated = decoded.get("VALIDATED_VALUES", {})
        if validated:
            self.data.update(validated)
            self.async_set_updated_data(self.data)

    async def _ensure_writable(self) -> None:
        """Ensure the BLE client is connected and ready for a write."""
        if not self._connected:
            try:
                await self._connect()
            except UpdateFailed as err:
                raise HomeAssistantError(str(err)) from err
        if (
            not self._client or not self._client.is_connected
        ):  # pragma: no cover - guarded by _connect above
            self._connected = False
            raise HomeAssistantError(f"Not connected to {self.address}")

    async def _write(self, frame: bytes, description: str) -> None:
        """Write a frame to the BLE characteristic."""
        assert self._client is not None
        try:
            await self._client.write_gatt_char(SVS_CHAR_UUID, frame)
        except BleakError as err:
            self._connected = False
            raise HomeAssistantError(f"{description}: {err}") from err
        await asyncio.sleep(COMMAND_DELAY)

    async def async_send_command(self, param: str, value: Any) -> None:
        """Send a command to the subwoofer.

        Raises HomeAssistantError on connection or write errors.
        """
        async with self._command_lock:
            await self._ensure_writable()

            frame, _ = svs_encode("MEMWRITE", param, value)
            if not frame:
                raise HomeAssistantError(
                    f"Failed to encode command for {param}={value}"
                )

            await self._write(frame, f"Failed to send {param}")

            # Optimistic update — the SVS device does not reliably push a
            # notification after a write, so reflect the new value locally so
            # all entities, services, and sync_from stay consistent.
            self.data[param] = value
            if param in SYNCABLE_PARAMS and self.data.get("ACTIVE_PRESET") is not None:
                self.data["ACTIVE_PRESET"] = None
            self.async_set_updated_data(self.data)

    async def async_load_preset(self, preset_number: int) -> None:
        """Load a preset on the subwoofer."""
        if not 1 <= preset_number <= 4:
            raise ValueError(f"Invalid preset number: {preset_number}")

        async with self._command_lock:
            await self._ensure_writable()

            frame, _ = svs_encode("PRESETLOADSAVE", f"PRESET{preset_number}LOAD")
            if not frame:  # pragma: no cover - guarded by range check above
                raise HomeAssistantError(
                    f"Failed to encode preset {preset_number} load"
                )

            await self._write(frame, f"Failed to load preset {preset_number}")

            self.data["ACTIVE_PRESET"] = preset_number
            self.async_set_updated_data(self.data)
            await self._request_full_settings()
            subtype = (
                TRIGGER_SUBTYPE_DEFAULT
                if preset_number == 4
                else f"preset_{preset_number}"
            )
            self._fire_event(TRIGGER_TYPE_PRESET_LOADED, subtype)

    async def async_save_preset(self, preset_number: int) -> None:
        """Save current settings to a preset slot (1-3)."""
        if not 1 <= preset_number <= 3:
            raise ValueError(
                f"Invalid preset number for save: {preset_number} (must be 1-3)"
            )

        async with self._command_lock:
            await self._ensure_writable()

            frame, _ = svs_encode("PRESETLOADSAVE", f"PRESET{preset_number}SAVE")
            if not frame:  # pragma: no cover - guarded by range check above
                raise HomeAssistantError(
                    f"Failed to encode preset {preset_number} save"
                )

            await self._write(frame, f"Failed to save preset {preset_number}")

    async def _request_full_settings(self) -> None:
        """Request all settings from the subwoofer."""
        if (
            not self._client or not self._connected
        ):  # pragma: no cover - guarded by callers
            return

        requests = [
            ("MEMREAD", "FULL_SETTINGS"),
            ("MEMREAD", "PRESET1NAME"),
            ("MEMREAD", "PRESET2NAME"),
            ("MEMREAD", "PRESET3NAME"),
        ]
        for ftype, param in requests:
            frame, _ = svs_encode(ftype, param)
            if not frame:  # pragma: no cover - all entries are valid params
                continue
            try:
                await self._client.write_gatt_char(SVS_CHAR_UUID, frame)
            except BleakError as err:
                _LOGGER.warning("Failed to request %s: %s", param, err)
                return
            await asyncio.sleep(COMMAND_DELAY)

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._disconnect_lock:
            if self._client and self._client.is_connected:
                with contextlib.suppress(BleakError):
                    await self._client.disconnect()
            self._connected = False
            self._client = None

    async def async_request_refresh_data(self) -> None:
        """Request a refresh of all data from the subwoofer."""
        if self._connected:
            await self._request_full_settings()
