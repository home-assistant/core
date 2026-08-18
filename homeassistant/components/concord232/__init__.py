"""The Concord232 integration."""

from concord232 import client as concord232_client

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant

from .coordinator import Concord232ConfigEntry, Concord232Coordinator

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]


def build_url(host: str, port: int, use_ssl: bool) -> str:
    """Return the server url for the stored connection settings."""
    protocol = "https" if use_ssl else "http"
    return f"{protocol}://{host}:{port}"


async def async_setup_entry(hass: HomeAssistant, entry: Concord232ConfigEntry) -> bool:
    """Set up Concord232 from a config entry."""
    url = build_url(entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_SSL])
    client = await hass.async_add_executor_job(concord232_client.Client, url)
    coordinator = Concord232Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Concord232ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
