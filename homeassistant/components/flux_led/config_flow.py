"""Config flow for Flux LED/MagicLight."""
from flux_led import BulbScanner

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    bulb_scanner = BulbScanner()
    devices = bulb_scanner.scan()
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Flux LED/MagicLight", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN
)
