"""The Flic Button integration."""

from __future__ import annotations

import contextlib
import logging

from bleak import BleakError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN as DOMAIN,
    DeviceType,
    PushTwistMode,
)
from .coordinator import FlicCoordinator
from .flic_client import FlicClient, FlicProtocolError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
]

type FlicButtonConfigEntry = ConfigEntry[FlicCoordinator]


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

    # Create coordinator
    coordinator = FlicCoordinator(hass, client, entry, serial_number, battery_level)
    entry.runtime_data = coordinator

    # Load persisted slot values for Twist devices
    await coordinator.async_load_slot_values()

    # Try to connect if device is currently available
    if ble_device:
        try:
            await coordinator.async_connect()
        except (TimeoutError, BleakError, FlicProtocolError):
            _LOGGER.debug(
                "Initial connection to %s failed, will retry when device is available",
                address,
            )

    # Register BLE callback for connection/reconnection
    @callback
    def _async_bluetooth_callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle Bluetooth updates for connection/reconnection."""
        coordinator.client.ble_device = service_info.device
        hass.async_create_task(coordinator.async_reconnect_if_needed())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_callback,
            BluetoothCallbackMatcher({CONF_ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    # Listen for options updates (reload integration when push_twist_mode changes)
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_options_updated(
    hass: HomeAssistant, entry: FlicButtonConfigEntry
) -> None:
    """Handle options update."""
    # Reload the integration to apply new push_twist_mode
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FlicButtonConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data:
        await entry.runtime_data.async_disconnect()
    return unload_ok
