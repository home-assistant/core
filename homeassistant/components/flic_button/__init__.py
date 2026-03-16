"""The Flic Button integration."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import logging
from typing import Any

from bleak import BleakError
from pyflic_ble import FlicClient, FlicProtocolError, FlicState

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_device_registry_updated_event

from .const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    FLIC_BUTTON_EVENT,
    DeviceType,
    PushTwistMode,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.EVENT,
]


@dataclass
class FlicButtonData:
    """Runtime data for a Flic Button config entry."""

    client: FlicClient
    serial_number: str | None
    battery_level: int | None


type FlicButtonConfigEntry = ConfigEntry[FlicButtonData]


async def async_setup_entry(hass: HomeAssistant, entry: FlicButtonConfigEntry) -> bool:
    """Set up Flic Button from a config entry."""

    address: str = entry.data[CONF_ADDRESS]

    # Try to get BLE device (may be None if device is not in range)
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )

    # Load pairing key from hex string
    pairing_key = bytes.fromhex(entry.data[CONF_PAIRING_KEY])

    # Get serial number (may not exist for older config entries)
    serial_number = entry.data.get(CONF_SERIAL_NUMBER)

    # Get battery level from pairing (may not exist for older config entries)
    battery_level = entry.data.get(CONF_BATTERY_LEVEL)

    # Get device type from config entry (may not exist for older config entries)
    device_type_str = entry.data.get(CONF_DEVICE_TYPE)
    device_type: DeviceType | None = None
    if device_type_str:
        with contextlib.suppress(ValueError):
            device_type = DeviceType(device_type_str)

    # Get sig_bits for Twist quick verify (may not exist for older config entries)
    sig_bits = entry.data.get(CONF_SIG_BITS, 0)

    # Get push_twist_mode option for Twist devices
    push_twist_mode_str = entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
    try:
        push_twist_mode = PushTwistMode(push_twist_mode_str)
    except ValueError:
        push_twist_mode = PushTwistMode.DEFAULT

    # Create client with stored pairing credentials and device type
    # ble_device may be None if the device is not currently in range
    client = FlicClient(
        address=address,
        ble_device=ble_device,
        pairing_id=entry.data[CONF_PAIRING_ID],
        pairing_key=pairing_key,
        serial_number=serial_number,
        device_type=device_type,
        sig_bits=sig_bits,
        push_twist_mode=push_twist_mode,
    )

    # Store runtime data
    entry.runtime_data = FlicButtonData(
        client=client,
        serial_number=serial_number,
        battery_level=battery_level,
    )

    # Try to connect if device is currently available
    if ble_device:
        try:
            await client.start()
        except TimeoutError, BleakError, FlicProtocolError:
            _LOGGER.debug(
                "Initial connection to %s failed, will retry when device is available",
                address,
            )

    # Register BLE callback AFTER initial connection attempt to prevent
    # a BLE advertisement from triggering async_reconnect() concurrently
    # with the start() call above.
    @callback
    def _async_bluetooth_callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle Bluetooth updates for connection/reconnection."""
        client.set_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_callback,
            BluetoothCallbackMatcher({CONF_ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    # Look up device_id for bus events
    device_id: str | None = None
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, client.address)})
    if device:
        device_id = device.id

    # Register bus event callbacks (for automations)
    @callback
    def _fire_button_bus_event(event_type: str, event_data: dict[str, Any]) -> None:
        """Fire a Home Assistant bus event for button events."""
        hass.bus.async_fire(
            FLIC_BUTTON_EVENT,
            {
                "device_id": device_id,
                "address": client.address,
                "event_type": event_type,
                **event_data,
            },
        )

    entry.async_on_unload(client.register_button_event_callback(_fire_button_bus_event))
    entry.async_on_unload(client.register_rotate_event_callback(_fire_button_bus_event))

    # Register state callback for device registry updates on connect
    @callback
    def _handle_state_change(state: FlicState) -> None:
        """Update device registry when connection state changes."""
        if not state.connected:
            return

        device_registry_inner = dr.async_get(hass)
        device_entry = device_registry_inner.async_get_device(
            identifiers={(DOMAIN, client.address)}
        )
        if not device_entry:
            return

        if state.firmware_version is not None:
            device_registry_inner.async_update_device(
                device_entry.id,
                sw_version=str(state.firmware_version),
            )
        if state.device_name and device_entry.name_by_user is None:
            device_registry_inner.async_update_device(
                device_entry.id,
                name_by_user=state.device_name,
            )
            _LOGGER.debug(
                "Synced device name from %s: %s",
                client.address,
                state.device_name,
            )

    entry.async_on_unload(client.register_state_callback(_handle_state_change))

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register device name listener to push HA renames to the physical device
    unsub = _register_device_name_listener(hass, entry, client)
    if unsub:
        entry.async_on_unload(unsub)

    # Reload entry when options change (e.g. push_twist_mode)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


@callback
def _register_device_name_listener(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    client: FlicClient,
) -> CALLBACK_TYPE | None:
    """Register a listener to push HA device renames to the physical device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, client.address)})
    if not device:
        return None

    @callback
    def _async_on_device_registry_update(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Handle device registry updates."""
        if event.data["action"] != "update":
            return
        if "name_by_user" not in event.data["changes"]:
            return

        device_entry = device_registry.async_get(event.data["device_id"])
        if not device_entry or not device_entry.name_by_user:
            return

        hass.async_create_background_task(
            _async_push_name_to_device(client, device_entry.name_by_user),
            name=f"{DOMAIN}_push_name_{client.address}",
        )

    return async_track_device_registry_updated_event(
        hass,
        device.id,
        _async_on_device_registry_update,
    )


async def _async_push_name_to_device(client: FlicClient, name: str) -> None:
    """Push a name change to the physical device."""
    if not client.state.connected or not client.is_connected:
        _LOGGER.debug(
            "Cannot push name to %s: device not connected",
            client.address,
        )
        return

    try:
        confirmed_name, _ = await client.set_name(name)
        _LOGGER.debug(
            "Pushed name to %s: %s (confirmed: %s)",
            client.address,
            name,
            confirmed_name,
        )
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Failed to push name to %s",
            client.address,
        )


async def _async_update_listener(
    hass: HomeAssistant, entry: FlicButtonConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FlicButtonConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.stop()

    return unload_ok
