"""The Flic Button integration."""

from __future__ import annotations

from dataclasses import dataclass

from bleak import BleakError
from pyflic_ble import FlicClient, FlicProtocolError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DeviceType,
    PushTwistMode,
)

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
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    pairing_key = bytes.fromhex(entry.data[CONF_PAIRING_KEY])
    serial_number = entry.data.get(CONF_SERIAL_NUMBER)
    battery_level = entry.data.get(CONF_BATTERY_LEVEL)
    device_type = DeviceType(entry.data[CONF_DEVICE_TYPE])
    sig_bits = entry.data.get(CONF_SIG_BITS, 0)
    push_twist_mode = PushTwistMode(
        entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
    )

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

    entry.runtime_data = FlicButtonData(
        client=client,
        serial_number=serial_number,
        battery_level=battery_level,
    )

    if ble_device:
        try:
            await client.start()
        except (TimeoutError, BleakError, FlicProtocolError) as err:
            raise ConfigEntryNotReady(f"Unable to connect to {address}") from err

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options change (e.g. push_twist_mode)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


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
