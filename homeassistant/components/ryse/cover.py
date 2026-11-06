"""Support for RYSE Smart Shades via BLE."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import partial
import logging
from typing import Any, override

from bleak import BleakClient, BleakError
from ryseble.device import RyseBLEDevice

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RyseConfigEntry, _async_unpair
from .const import MANUFACTURER_NAME

PARALLEL_UPDATES = 1  # one BLE connection at a time
_RECONNECT_COOLDOWN = 5.0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RYSE Smart Shade cover from a config entry."""
    device = entry.runtime_data
    async_add_entities([RyseCoverEntity(device, entry)])


class RyseCoverEntity(CoverEntity):
    """Representation of a RYSE Smart Shade BLE cover entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, device: RyseBLEDevice, config_entry: RyseConfigEntry) -> None:
        """Initialize the Smart Shade cover entity."""
        self._device = device
        self._config_entry = config_entry
        self._connect_lock = asyncio.Lock()
        self._expected_disconnect = False
        self._reconnect_when_seen = False
        self._reconnect_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None

        self._attr_unique_id = device.address
        self._current_position: int | None = None
        self._attr_is_closed: bool | None = None
        self._attr_available = True
        self._attr_device_info = DeviceInfo(
            manufacturer=MANUFACTURER_NAME,
            model="SmartShade BLE",
            connections={(CONNECTION_BLUETOOTH, self._device.address)},
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._device.update_callback = self._update_position
        self.async_on_remove(self._clear_callback)
        self._reconnect_debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=_RECONNECT_COOLDOWN,
            immediate=True,
            function=self._async_reconnect,
        )
        self.async_on_remove(self._reconnect_debouncer.async_shutdown)
        self.async_on_remove(
            async_register_callback(
                self.hass,
                self._async_ble_advertisement,
                BluetoothCallbackMatcher(
                    address=self._device.address, connectable=True
                ),
                BluetoothScanningMode.PASSIVE,
            )
        )
        self._async_attach_disconnect_callback()
        client = self._device.client
        if client and client.is_connected:
            try:
                await self._device.send_get_position()
            except (TimeoutError, OSError, EOFError, BleakError) as err:
                _LOGGER.debug("Could not request initial cover position: %s", err)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Ignore the GATT disconnect that unload itself causes."""
        self._expected_disconnect = True
        await super().async_will_remove_from_hass()

    def _clear_callback(self) -> None:
        """Restore the constructor default so ryseble will not await this entity.

        Assign ``None`` rather than deleting the attribute: the library object
        is constructed with ``update_callback = None``.
        """
        if self._device.update_callback == self._update_position:
            self._device.update_callback = None

    def _is_connected(self) -> bool:
        """Return True when the BLE client is present and connected."""
        client = self._device.client
        return bool(client and client.is_connected)

    def _async_attach_disconnect_callback(self) -> None:
        """Watch the current GATT client so availability is not delayed 15s."""
        client = self._device.client
        if client is None:
            return
        client.set_disconnected_callback(self._on_ble_disconnect)

    def _on_ble_disconnect(self, _client: BleakClient) -> None:
        """Handle a GATT disconnect, which may arrive off the event loop."""
        self.hass.loop.call_soon_threadsafe(self._async_ble_disconnected)

    @callback
    def _async_ble_disconnected(self) -> None:
        """Mark the cover unavailable as soon as the GATT link drops."""
        if self._expected_disconnect:
            return
        self._reconnect_when_seen = True
        self._clear_cached_position()
        self._set_available(False, "disconnected")
        self.async_write_ha_state()
        client = self._device.client
        self._config_entry.async_create_background_task(
            self.hass,
            self._async_cleanup_disconnected_client(client),
            f"{self.entity_id} disconnect cleanup",
        )

    @callback
    def _async_ble_advertisement(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Reconnect once the shade is advertising again after a dropped link."""
        if not self._reconnect_when_seen or self._is_connected():
            return
        if self._reconnect_debouncer is not None:
            self._reconnect_debouncer.async_schedule_call()

    async def _async_cleanup_disconnected_client(
        self, client: BleakClient | None
    ) -> None:
        """Drop the stale client after an unexpected GATT disconnect."""
        async with self._connect_lock:
            if self._device.client is not client:
                return
            self._expected_disconnect = True
            try:
                await _async_unpair(self._device)
            finally:
                self._expected_disconnect = False

    async def _async_drop_client(self, reason: str) -> None:
        """Release the BLE link and wait for a later advertisement to reconnect."""
        self._reconnect_when_seen = True
        async with self._connect_lock:
            self._expected_disconnect = True
            try:
                await _async_unpair(self._device)
            finally:
                self._expected_disconnect = False
        self._clear_cached_position()
        self._set_available(False, reason)

    async def _async_reconnect(self) -> None:
        """Pair again after the shade is seen advertising."""
        if self._expected_disconnect or self._is_connected():
            return
        if any(self._config_entry.async_get_active_flows(self.hass, {SOURCE_REAUTH})):
            return
        if not await self._async_ensure_connected():
            self.async_write_ha_state()
            return
        try:
            await self._device.send_get_position()
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            await self._async_drop_client(str(err))
        else:
            self._reconnect_when_seen = False
            self._set_available(True)
        self.async_write_ha_state()

    def _set_available(self, available: bool, reason: str | None = None) -> None:
        """Update availability, logging once on each transition."""
        if available == self._attr_available:
            return
        if available:
            _LOGGER.info("%s is available again", self.entity_id)
        else:
            _LOGGER.info("%s became unavailable: %s", self.entity_id, reason)
        self._attr_available = available

    def _clear_cached_position(self) -> None:
        """Drop cached cover state so a later poll will request a fresh position."""
        self._current_position = None
        self._attr_is_closed = None

    def _cached_position_is_valid(self) -> bool:
        """Return True when the cached Home Assistant position is still usable."""
        return self._current_position is not None and self._device.is_valid_position(
            self._current_position
        )

    async def _update_position(self, position: int) -> None:
        """Update cover position when receiving notification."""
        if self._device.is_valid_position(position):
            real_position = self._device.get_real_position(position)
            self._current_position = real_position
            self._attr_is_closed = self._device.is_closed(position)
            self._set_available(True)
            _LOGGER.debug(
                "Updated cover position: raw=%d mapped=%d", position, real_position
            )
        else:
            _LOGGER.warning("Invalid position value detected: %d", position)
            self._clear_cached_position()
        self.async_write_ha_state()

    async def _async_ensure_connected(self) -> bool:
        """Reconnect when the BLE client is missing or dropped.

        ryseble's writes are no-ops when ``client`` is None, so a command that
        runs after a failed poll would otherwise appear to succeed.
        """
        async with self._connect_lock:
            if self._is_connected():
                self._async_attach_disconnect_callback()
                return True
            if await self._device.pair():
                self._async_attach_disconnect_callback()
                return True
            self._expected_disconnect = True
            try:
                await _async_unpair(self._device)
            finally:
                self._expected_disconnect = False
            self._reconnect_when_seen = True
            self._set_available(False, "failed to pair")
            self._config_entry.async_start_reauth(self.hass)
            return False

    async def _async_send_command(
        self, description: str, send: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Send a cover command, reconnecting first if needed."""
        try:
            if not await self._async_ensure_connected():
                self.async_write_ha_state()
                raise HomeAssistantError(f"Failed to {description}: failed to pair")
            await send()
            self._reconnect_when_seen = False
            self._set_available(True)
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            raise HomeAssistantError(f"Failed to {description}: {err}") from err

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shade."""
        await self._async_send_command("open cover", self._device.send_open)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shade."""
        await self._async_send_command("close cover", self._device.send_close)

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the shade to a specific position."""
        ha_position = kwargs[ATTR_POSITION]
        device_position = self._device.get_real_position(ha_position)
        await self._async_send_command(
            "set cover position",
            partial(self._device.send_set_position, device_position),
        )

    async def async_update(self) -> None:
        """Fetch the current state and position from a connected shade.

        Do not pair here: ryseble logs ERROR on a failed pair(), which would
        spam every 15s while the shade is out of range.
        """
        if not self._is_connected():
            return
        self._async_attach_disconnect_callback()
        try:
            if (
                self._current_position is not None
                and not self._cached_position_is_valid()
            ):
                self._clear_cached_position()

            if self._current_position is None:
                await self._device.send_get_position()

            self._reconnect_when_seen = False
            self._set_available(True)

        except (TimeoutError, OSError, EOFError, BleakError) as err:
            await self._async_drop_client(str(err))

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        return self._current_position
