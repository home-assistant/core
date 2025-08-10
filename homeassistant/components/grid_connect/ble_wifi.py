"""BLE utilities for sending Wi-Fi credentials to Grid Connect devices. Replace UUIDs and logic with actual device details as needed."""

import logging

# Import BleakClient or use stub for testing and async context support
try:
    from bleak import BleakClient as _OriginalBleakClient
except ImportError:
    _OriginalBleakClient = None

# BaseClient is either the real BleakClient or a stub
if _OriginalBleakClient:
    BaseClient = _OriginalBleakClient
else:
    class BaseClient:
        """Stub BleakClient when bleak is not available"""
        def __init__(self, address: str, timeout: int = None):
            pass
        async def is_connected(self) -> bool:
            return False
        async def write_gatt_char(self, char_uuid: str, data: bytes, response: bool = False):
            pass

class BleakClient(BaseClient):
    """Wrapper to provide async context management"""
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Ensure BleakClient supports async context management
if _OriginalBleakClient:
    class BleakClient(_OriginalBleakClient):
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass



# Placeholder UUIDs - replace with actual Grid Connect service/characteristic UUIDs
grid_connect_service_uuid = "0000fd88-0000-1000-8000-00805f9b34fb"
wifi_write_char_uuid = "0000fd89-0000-1000-8000-00805f9b34fb"

def format_wifi_payload(ssid: str, password: str) -> bytes:
    """Format the payload for the device (update as needed)."""
    # Example: simple comma-separated string (replace with actual protocol)
    return f"{ssid},{password}".encode()

async def send_wifi_credentials(address: str, ssid: str, password: str, timeout: int = 15) -> str | None:
    """Connect to BLE device and send Wi-Fi credentials. Returns None on success, error string on failure."""
    if not BleakClient:
        return "bleak_not_installed"
    client = BleakClient(address, timeout=timeout)
    try:
        if not await client.is_connected():
            return "not_connected"
        payload = format_wifi_payload(ssid, password)
        await client.write_gatt_char(wifi_write_char_uuid, payload, response=True)
        return None  # Success
    except ImportError:
        logging.getLogger(__name__).exception("Bleak import failed")
        return "bleak_import_error"
    except TimeoutError:
        logging.getLogger(__name__).exception("BLE operation timed out")
        return "timeout"
    except Exception:
        logging.getLogger(__name__).exception("Unexpected BLE Wi-Fi credential send error")
        raise
