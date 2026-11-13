"""Support for RYSE Smart Shades via BLE."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import partial
import logging
from typing import Any, override

from bleak import BleakClient, BleakError
from ryseble.device import RyseAuthenticationFailed, RyseBLEDevice

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_register_advertisement_callback,
)
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
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
from .const import DOMAIN, MANUFACTURER_NAME
from .helpers import async_best_local_scanner_device

PARALLEL_UPDATES = 1
_RECONNECT_COOLDOWN = 5.0
_RECONNECT_COOLDOWN_MAX = 300.0
# A reset shade on Home Assistant OS fails start_notify as a transport error,
# so one radio glitch must not ask the user to press PAIR.
_REAUTH_AFTER_LOCAL_FAILURES = 3

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

    _attr_device_class = CoverDeviceClass.SHADE
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
        self._removing = False
        self._released_client: BleakClient | None = None
        self._reconnect_when_seen = False
        self._reconnect_failures = 0
        self._local_failures = 0
        self._local_pair_attempt = False
        self._reconnect_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None

        self._attr_unique_id = device.address
        self._attr_current_cover_position: int | None = None
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
        self._device.disconnected_callback = self._on_ble_disconnect
        self.async_on_remove(self._clear_callback)
        self._reconnect_debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=_RECONNECT_COOLDOWN,
            immediate=True,
            function=self._async_reconnect,
            background=True,
        )
        self.async_on_remove(self._reconnect_debouncer.async_shutdown)
        # Fires for unchanged advertisements. The change callback does not, so a
        # shade with a static advert would otherwise stay unavailable.
        self.async_on_remove(
            async_register_advertisement_callback(
                self.hass,
                self._async_ble_advertisement,
                self._device.address,
            )
        )
        client = self._device.client
        if client and client.is_connected:
            try:
                await self._device.send_get_position()
            except (TimeoutError, OSError, EOFError, BleakError) as err:
                _LOGGER.debug("Could not request initial cover position: %s", err)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Ignore the GATT disconnect that unload itself causes."""
        self._removing = True
        # Wait for an in-flight pair() so unload can release that client.
        async with self._connect_lock:
            pass
        await super().async_will_remove_from_hass()

    def _clear_callback(self) -> None:
        """Drop this entity's callbacks so a removed entity is not awaited."""
        if self._device.update_callback == self._update_position:
            self._device.update_callback = None
        if self._device.disconnected_callback == self._on_ble_disconnect:
            self._device.disconnected_callback = None

    def _is_connected(self) -> bool:
        """Return True when the BLE client is present and connected."""
        client = self._device.client
        return bool(client and client.is_connected)

    def _on_ble_disconnect(self, client: BleakClient) -> None:
        """Handle a GATT disconnect, which may arrive off the event loop."""
        self.hass.loop.call_soon_threadsafe(self._async_ble_disconnected, client)

    @callback
    def _async_ble_disconnected(self, client: BleakClient) -> None:
        """Mark the cover unavailable as soon as the GATT link drops."""
        if self._removing or client is self._released_client:
            return
        current = self._device.client
        # A reconnect can replace the client before this deferred handler runs.
        if current is not None and current is not client:
            return
        self._reconnect_when_seen = True
        self._clear_cached_position()
        self._set_available(False, "disconnected")
        self.async_write_ha_state()
        self._config_entry.async_create_background_task(
            self.hass,
            self._async_cleanup_disconnected_client(client),
            f"{self.entity_id} disconnect cleanup",
        )

    @callback
    def _async_ble_advertisement(
        self, _service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Reconnect once the shade is advertising again after a dropped link."""
        if not self._reconnect_when_seen or self._is_connected():
            return
        if self._reconnect_debouncer is not None:
            self._reconnect_debouncer.async_schedule_call()

    async def _async_release_client(self) -> None:
        """Unpair while ignoring the GATT disconnect this unpair causes."""
        self._released_client = self._device.client
        await _async_unpair(self._device)

    async def _async_cleanup_disconnected_client(
        self, client: BleakClient | None
    ) -> None:
        """Drop the stale client after an unexpected GATT disconnect."""
        async with self._connect_lock:
            if self._device.client is not client:
                return
            await self._async_release_client()

    async def _async_drop_client(self, reason: str) -> None:
        """Release the BLE link and wait for a later advertisement to reconnect."""
        self._reconnect_when_seen = True
        async with self._connect_lock:
            await self._async_release_client()
        self._clear_cached_position()
        self._set_available(False, reason)

    async def _async_reconnect(self) -> None:
        """Pair again after the shade is seen advertising."""
        if self._removing or self._is_connected():
            return
        if any(self._config_entry.async_get_active_flows(self.hass, {SOURCE_REAUTH})):
            return
        try:
            if not await self._async_ensure_connected():
                if not self._removing:
                    self._note_pair_failure()
                    self.async_write_ha_state()
                return
            if self._removing:
                return
            await self._device.send_get_position()
        except RyseAuthenticationFailed as err:
            if self._removing:
                return
            self._note_reconnect_failure()
            await self._async_drop_client(str(err))
            self._config_entry.async_start_reauth(self.hass)
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            if self._removing:
                return
            self._note_local_failure()
            await self._async_drop_client(str(err))
        except Exception:
            if self._removing:
                return
            # Swallow so the debouncer does not log a second traceback.
            _LOGGER.debug(
                "Unexpected error reconnecting to %s",
                self._device.address,
                exc_info=True,
            )
            self._note_local_failure()
            await self._async_drop_client("unexpected error")
        else:
            if self._removing:
                return
            self._note_reconnect_success()
            self._reconnect_when_seen = False
            self._set_available(True)
        self.async_write_ha_state()

    def _note_reconnect_failure(self) -> None:
        """Lengthen the wait after each consecutive reconnect failure."""
        self._reconnect_failures += 1
        if self._reconnect_debouncer is None:
            return
        delay = (
            _RECONNECT_COOLDOWN
            if self._reconnect_failures == 1
            else self._reconnect_debouncer.cooldown * 2
        )
        self._reconnect_debouncer.cooldown = min(delay, _RECONNECT_COOLDOWN_MAX)

    def _note_pair_failure(self) -> None:
        """Back off, and count the failure toward reauth when a local adapter saw it."""
        if self._local_pair_attempt:
            self._note_local_failure()
            return
        self._note_reconnect_failure()

    def _note_local_failure(self) -> None:
        """Back off and ask for re-pairing after repeated local failures."""
        self._local_failures += 1
        self._note_reconnect_failure()
        if self._local_failures < _REAUTH_AFTER_LOCAL_FAILURES:
            return
        if any(self._config_entry.async_get_active_flows(self.hass, {SOURCE_REAUTH})):
            return
        self._config_entry.async_start_reauth(self.hass)

    def _note_reconnect_success(self) -> None:
        """Restore the short reconnect interval after a successful bond."""
        self._reconnect_failures = 0
        self._local_failures = 0
        if self._reconnect_debouncer is not None:
            self._reconnect_debouncer.cooldown = _RECONNECT_COOLDOWN

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
        self._attr_current_cover_position = None
        self._attr_is_closed = None

    def _cached_position_is_valid(self) -> bool:
        """Return True when the cached Home Assistant position is still usable."""
        return (
            self._attr_current_cover_position is not None
            and self._device.is_valid_position(self._attr_current_cover_position)
        )

    async def _update_position(self, position: int) -> None:
        """Update cover position when receiving notification."""
        if self._device.is_valid_position(position):
            real_position = self._device.get_real_position(position)
            self._attr_current_cover_position = real_position
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

        ``pair()`` returning False is not a confirmed bond rejection.
        ``RyseAuthenticationFailed`` is, and the caller starts reauthentication.
        """
        async with self._connect_lock:
            if self._removing:
                return False
            if self._is_connected():
                return True
            paired = await self._async_pair_on_local_adapter()
            if paired:
                if self._removing:
                    await self._async_release_client()
                    return False
                self._released_client = None
                return True
            await self._async_release_client()
            if self._removing:
                return False
            self._reconnect_when_seen = True
            self._set_available(
                False, "no local adapter" if paired is None else "failed to pair"
            )
            return False

    async def _async_pair_on_local_adapter(self) -> bool | None:
        """Pair when a local adapter sees the shade.

        A proxy-only sighting is refused because the BlueZ agent cannot pair
        through it. The Bluetooth stack still chooses the connection backend.

        Returns True on success, None when no local adapter currently sees the
        shade, and False only when the library has neither a device nor an
        address. False is not a confirmed bond rejection.
        """
        scanner_device = async_best_local_scanner_device(
            self.hass, self._device.address
        )
        self._local_pair_attempt = scanner_device is not None
        if scanner_device is None:
            return None
        self._device.set_ble_device(scanner_device.ble_device)
        return await self._device.pair()

    async def _async_send_command(
        self, description: str, send: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Send a cover command, reconnecting first if needed."""
        if any(self._config_entry.async_get_active_flows(self.hass, {SOURCE_REAUTH})):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reauth_in_progress",
            )
        try:
            if not await self._async_ensure_connected():
                self._note_pair_failure()
                self.async_write_ha_state()
                raise HomeAssistantError(f"Failed to {description}: failed to pair")
            await send()
            self._note_reconnect_success()
            self._reconnect_when_seen = False
            self._set_available(True)
        except RyseAuthenticationFailed as err:
            self._note_reconnect_failure()
            await self._async_drop_client(str(err))
            self._config_entry.async_start_reauth(self.hass)
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to {description}: {err}") from err
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            self._note_local_failure()
            await self._async_drop_client(str(err))
            self.async_write_ha_state()
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

        Do not pair here. Reconnect is driven by advertisements, including
        ones whose payload has not changed, and backs off after failures.
        """
        if not self._is_connected():
            return
        try:
            if (
                self._attr_current_cover_position is not None
                and not self._cached_position_is_valid()
            ):
                self._clear_cached_position()

            if self._attr_current_cover_position is None:
                await self._device.send_get_position()

            self._reconnect_when_seen = False
            self._set_available(True)

        except (TimeoutError, OSError, EOFError, BleakError) as err:
            await self._async_drop_client(str(err))
