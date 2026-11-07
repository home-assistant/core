"""The Candy House Sesame BLE integration."""

import asyncio
from collections.abc import Callable
import contextlib
import logging
from typing import Any
import uuid

from pysesame_ble import (
    ProductModels,
    SesameAdData,
    SesameAuthenticationError,
    SesameKeyError,
    SesameLock,
    get_sesame_mfg_data,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_DEVICE_UUID,
    CONF_SECRET_KEY,
    DOMAIN,
    INITIAL_RECONNECT_BACKOFF,
    MAX_RECONNECT_BACKOFF,
    RECONNECT_BACKOFF_MULTIPLIER,
)

logger = logging.getLogger(__name__)

PLATFORMS = [
    Platform.LOCK,
]

type SesameBleConfigEntry = ConfigEntry[SesameDeviceWrapper]


class SesameDeviceWrapper:
    """Manages the connection, state, and coordination of a Sesame BLE lock."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SesameBleConfigEntry,
        ble_device: Any,
        adv_data: SesameAdData,
        secret_key: str,
        model_name: str,
    ) -> None:
        """Initialize the device wrapper."""
        self.hass = hass
        self.entry = entry
        self.ble_device = ble_device
        self.adv_data = adv_data
        self.secret_key = secret_key
        self.model_name = model_name
        self.update_listeners: list[Callable[[], None]] = []
        self._is_unloading = False
        self._connect_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_timer: CALLBACK_TYPE | None = None
        self._reconnect_backoff: float = INITIAL_RECONNECT_BACKOFF

        self.device = SesameLock(
            ble_device,
            adv_data,
            secret_key=secret_key,
            status_callback=self._handle_status_update,
            disconnect_callback=self._handle_device_disconnect,
        )

    def _handle_device_disconnect(self) -> None:
        """Handle disconnection from device."""
        if not self._is_unloading:
            logger.warning(
                "Sesame BLE %s disconnected unexpectedly",
                self.mac_address,
            )
        self.hass.loop.call_soon_threadsafe(self._handle_unexpected_disconnect)

    @callback
    def _handle_unexpected_disconnect(self) -> None:
        """Handle unexpected disconnect on the event loop."""
        self._notify_update_listeners()
        self.schedule_reconnect()

    @property
    def mac_address(self) -> str:
        """Return the MAC address."""
        return str(self.entry.data["mac_address"])

    @property
    def fw_version(self) -> str | None:
        """Return the firmware version if known."""
        return getattr(self.device, "fw_version", None)

    @property
    def available(self) -> bool:
        """Return True if device is logged in or recently seen."""
        return bool(
            self.device.is_logged_in
            or bluetooth.async_ble_device_from_address(
                self.hass, self.mac_address, connectable=True
            )
            is not None
        )

    def register_update_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback for when the device state updates."""
        self.update_listeners.append(listener)

        def unregister() -> None:
            if listener in self.update_listeners:
                self.update_listeners.remove(listener)

        return unregister

    def notify_update_listeners(self) -> None:
        """Notify all entity listeners of a state change."""
        self._notify_update_listeners()

    def _notify_update_listeners(self) -> None:
        """Notify all entity listeners of a state change."""
        for listener in list(self.update_listeners):
            try:
                listener()
            except Exception:
                logger.exception("Error in Sesame update listener")

    def _handle_status_update(self, device: Any, status: Any) -> None:
        """Propagate state updates to all entity listeners."""
        self._notify_update_listeners()

    @property
    def is_unloading(self) -> bool:
        """Return True if the wrapper is currently unloading."""
        return self._is_unloading

    @property
    def is_connecting(self) -> bool:
        """Return True if connection is currently in progress."""
        return self._connect_lock.locked()

    async def async_connect(self) -> None:
        """Connect and authenticate with the device."""
        if self._is_unloading:
            return
        async with self._connect_lock:
            if self._is_unloading:
                return
            if not self.device.is_connected:
                await self.device.connect()
            if not self.device.is_logged_in:
                await self.device.login()
        self._reconnect_backoff = INITIAL_RECONNECT_BACKOFF
        if self._reconnect_timer is not None:
            self._reconnect_timer()
            self._reconnect_timer = None
        self._notify_update_listeners()

    @callback
    def cancel_reconnect(self) -> None:
        """Cancel any scheduled reconnect timer or running reconnect task."""
        if self._reconnect_timer is not None:
            self._reconnect_timer()
            self._reconnect_timer = None
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None

    @callback
    def schedule_reconnect(self) -> None:
        """Schedule reconnection with backoff if not already reconnecting or scheduled."""
        if (
            self._is_unloading
            or (self.device and self.device.is_connected and self.device.is_logged_in)
            or self._reconnect_timer is not None
            or (self._reconnect_task is not None and not self._reconnect_task.done())
        ):
            return

        self._reconnect_task = self.entry.async_create_background_task(
            self.hass,
            self._async_reconnect_with_backoff(),
            f"sesame_ble_reconnect_{self.mac_address}",
        )

    @callback
    def _schedule_retry_timer(self, delay: float) -> None:
        """Schedule a retry timer after a failed reconnection."""
        if self._is_unloading or (
            self.device and self.device.is_connected and self.device.is_logged_in
        ):
            return
        if self._reconnect_timer is not None:
            self._reconnect_timer()
        self._reconnect_timer = async_call_later(
            self.hass, delay, self._handle_reconnect_timer
        )

    @callback
    def _handle_reconnect_timer(self, _now: Any = None) -> None:
        """Handle reconnect timer firing."""
        self._reconnect_timer = None
        self.schedule_reconnect()

    async def _async_reconnect_with_backoff(self) -> None:
        """Attempt to reconnect with retry backoff on failure."""
        current_task = asyncio.current_task()
        if self._is_unloading or (
            self.device and self.device.is_connected and self.device.is_logged_in
        ):
            return

        try:
            await self.async_connect()
            self._reconnect_backoff = INITIAL_RECONNECT_BACKOFF
        except Exception as err:  # noqa: BLE001
            logger.debug(
                "Failed to reconnect to Sesame %s: %s; retrying in %.1fs",
                self.mac_address,
                err,
                self._reconnect_backoff,
            )
            if not self._is_unloading and (
                not self.device
                or not (self.device.is_connected and self.device.is_logged_in)
            ):
                delay = self._reconnect_backoff
                self._reconnect_backoff = min(
                    self._reconnect_backoff * RECONNECT_BACKOFF_MULTIPLIER,
                    MAX_RECONNECT_BACKOFF,
                )
                self._schedule_retry_timer(delay)
        finally:
            if self._reconnect_task is current_task:
                self._reconnect_task = None

    async def async_reconnect(self) -> None:
        """Attempt to reconnect after a disconnect or when advertisement is received."""
        await self._async_reconnect_with_backoff()

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        self._is_unloading = True
        self.cancel_reconnect()
        async with self._connect_lock:
            await self.device.disconnect()
        self._notify_update_listeners()


async def async_setup_entry(hass: HomeAssistant, entry: SesameBleConfigEntry) -> bool:
    """Set up Candy House Sesame BLE from a config entry."""
    mac_address = entry.data["mac_address"]
    secret_key = entry.data[CONF_SECRET_KEY]
    model_name = entry.data[CONF_MODEL]

    ble_device = bluetooth.async_ble_device_from_address(
        hass, mac_address, connectable=True
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"mac": mac_address},
        )

    adv_data = None
    bluetooth_adv = bluetooth.async_last_service_info(hass, mac_address)
    if bluetooth_adv:
        mfg_tuple = get_sesame_mfg_data(bluetooth_adv.manufacturer_data)
        if mfg_tuple:
            with contextlib.suppress(ValueError, KeyError, IndexError):
                adv_data = SesameAdData.decode(mfg_tuple[1])

    if adv_data is not None:
        expected_model = ProductModels[model_name]
        if adv_data.model_id != expected_model.value:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="device_mismatch",
                translation_placeholders={"mac": mac_address},
            )
        if not adv_data.is_registered:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_unregistered",
                translation_placeholders={"mac": mac_address},
            )
        if CONF_DEVICE_UUID in entry.data:
            expected_uuid = uuid.UUID(entry.data[CONF_DEVICE_UUID])
            if adv_data.device_uuid != expected_uuid:
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="device_mismatch",
                    translation_placeholders={"mac": mac_address},
                )
    else:
        if CONF_DEVICE_UUID not in entry.data:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"mac": mac_address},
            )
        product_model = ProductModels[model_name]
        adv_data = SesameAdData(
            model_id=product_model.value,
            is_registered=True,
            device_uuid=uuid.UUID(entry.data[CONF_DEVICE_UUID]),
        )

    wrapper = SesameDeviceWrapper(
        hass,
        entry,
        ble_device,
        adv_data,
        secret_key,
        model_name,
    )

    try:
        await wrapper.async_connect()
    except (SesameAuthenticationError, SesameKeyError) as err:
        with contextlib.suppress(Exception):
            await wrapper.async_disconnect()
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except Exception as err:
        with contextlib.suppress(Exception):
            await wrapper.async_disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={"mac": mac_address, "error": str(err)},
        ) from err

    entry.runtime_data = wrapper

    @callback
    def _handle_bluetooth_advertisement(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update the underlying BLEDevice when a new advertisement is received."""
        wrapper.ble_device = service_info.device
        if wrapper.device:
            wrapper.device.set_ble_device(service_info.device)
        wrapper.notify_update_listeners()
        wrapper.schedule_reconnect()

    @callback
    def _handle_bluetooth_unavailable(
        _service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Handle bluetooth device becoming unavailable."""
        wrapper.cancel_reconnect()
        wrapper.notify_update_listeners()

    entry.async_on_unload(wrapper.cancel_reconnect)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _handle_bluetooth_advertisement,
            bluetooth.BluetoothCallbackMatcher(
                address=ble_device.address, connectable=True
            ),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass,
            _handle_bluetooth_unavailable,
            ble_device.address,
            connectable=True,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SesameBleConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and getattr(entry, "runtime_data", None):
        await entry.runtime_data.async_disconnect()

    return unload_ok
