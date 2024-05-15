"""PSS BLE Scanner integration."""
import logging
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_register_callback,
    BluetoothChange,  # Import BluetoothChange
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pss_ble"
MANUFACTURER_ID = 0x0877  # Updated manufacturer ID

async def async_setup(hass, config):
    """Set up the PSS BLE Scanner component."""
    _LOGGER.info("Setting up PSS BLE Scanner component")

    def process_ble_advertisement(service_info: BluetoothServiceInfo, change: BluetoothChange):
        """Process a new BLE advertisement."""
        if service_info.manufacturer_data and MANUFACTURER_ID in service_info.manufacturer_data:
            _LOGGER.warning(f"Detected BLE device with Manufacturer ID: {MANUFACTURER_ID}")
            # Add your custom logic here, e.g., create a sensor entity, trigger an automation, etc.

    async_register_callback(hass, process_ble_advertisement, {"manufacturer_id": MANUFACTURER_ID}, BluetoothScanningMode.ACTIVE)

    return True
