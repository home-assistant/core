"""PSS BLE Scanner integration."""
import logging
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_register_callback,
    BluetoothChange,  # Import BluetoothChange
)
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pss_ble"
MANUFACTURER_ID = 0x0877  # Updated manufacturer ID

Devices = {}

async def async_setup(hass, config):
    """Set up the PSS BLE Scanner component."""
    _LOGGER.warning("Setting up PSS BLE Scanner component")

    def process_ble_advertisement(service_info: BluetoothServiceInfo, change: BluetoothChange):
        """Process a new BLE advertisement."""
        if service_info.manufacturer_data and MANUFACTURER_ID in service_info.manufacturer_data:
            _LOGGER.warning(f"Detected BLE device with Manufacturer ID: {MANUFACTURER_ID}, data: {service_info.manufacturer_data}")
            hass.data[DOMAIN] = {
              'battery' : service_info.manufacturer_data[MANUFACTURER_ID][3]
            }
            # Add your custom logic here, e.g., create a sensor entity, trigger an automation, etc.

    async_register_callback(hass, process_ble_advertisement, {"manufacturer_id": MANUFACTURER_ID}, BluetoothScanningMode.ACTIVE)

    hass.helpers.discovery.load_platform('sensor', DOMAIN, {}, config)

    return True
