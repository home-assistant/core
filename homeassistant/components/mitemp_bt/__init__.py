"""The mitemp_bt component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

DOMAIN = "mitemp_bt"

CONF_ADAPTER = "adapter"
CONF_CACHE = "cache_value"
CONF_MEDIAN = "median"
CONF_RETRIES = "retries"
CONF_TIMEOUT = "timeout"

DEFAULT_ADAPTER = "hci0"
DEFAULT_UPDATE_INTERVAL = 300
DEFAULT_FORCE_UPDATE = False
DEFAULT_MEDIAN = 3
DEFAULT_NAME = "Hygrothermograph"
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT = 10


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    config = entry.data
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, config.get(CONF_MAC))},
        name=DEFAULT_NAME,
        model="LYWSDCGQ",
        manufacturer="Xiaomi",
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    try:
        await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    except ValueError:
        pass
