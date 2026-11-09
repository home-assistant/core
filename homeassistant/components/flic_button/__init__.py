"""The Flic Button integration."""

from dataclasses import dataclass

from bleak import BleakError
from pyflic_ble import (
    DeviceType,
    FlicAuthenticationError,
    FlicClient,
    FlicProtocolError,
    FlicState,
    PushTwistMode,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DEVICE_TYPE_MODEL_NAMES,
    DOMAIN,
)

PLATFORMS: list[Platform] = [
    Platform.EVENT,
    Platform.NUMBER,
]


@dataclass
class FlicButtonData:
    """Runtime data for a Flic Button config entry."""

    client: FlicClient


type FlicButtonConfigEntry = ConfigEntry[FlicButtonData]


async def async_setup_entry(hass: HomeAssistant, entry: FlicButtonConfigEntry) -> None:
    """Set up Flic Button from a config entry."""

    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    pairing_key = bytes.fromhex(entry.data[CONF_PAIRING_KEY])
    serial_number = entry.data.get(CONF_SERIAL_NUMBER)
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

    entry.runtime_data = FlicButtonData(client=client)
    entry.async_on_unload(client.stop)

    # The firmware version is only known once the button is connected, so it is
    # left out here to keep the version stored from an earlier connection
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        manufacturer="Shortcut Labs",
        model=DEVICE_TYPE_MODEL_NAMES[device_type],
        serial_number=serial_number,
    )

    @callback
    def _async_state_updated(state: FlicState) -> None:
        """Store the firmware version when the button is connected."""
        if state.connected and state.firmware_version is not None:
            device_registry.async_update_device(
                device.id, sw_version=str(state.firmware_version)
            )

    # Registered before start() so the first connection is handled as well
    entry.async_on_unload(client.register_state_callback(_async_state_updated))

    if ble_device:
        try:
            await client.start()
        # The library raises FlicAuthenticationError only for a verify timeout
        except (
            TimeoutError,
            BleakError,
            FlicAuthenticationError,
            FlicProtocolError,
        ) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"address": address},
            ) from err

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

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def _async_update_listener(
    hass: HomeAssistant, entry: FlicButtonConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FlicButtonConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
