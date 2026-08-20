"""The Concord232 integration."""

from concord232 import client as concord232_client
from yarl import URL

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import Concord232ConfigEntry, Concord232Coordinator

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]


def build_url(host: str, port: int) -> str:
    """Return the server url for the stored connection settings."""
    # URL.build brackets IPv6 hosts correctly
    return str(URL.build(scheme="http", host=host, port=port))


async def async_setup_entry(hass: HomeAssistant, entry: Concord232ConfigEntry) -> bool:
    """Set up Concord232 from a config entry."""
    url = build_url(entry.data[CONF_HOST], entry.data[CONF_PORT])
    client = await hass.async_add_executor_job(concord232_client.Client, url)
    coordinator = Concord232Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: Concord232ConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Concord232ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
