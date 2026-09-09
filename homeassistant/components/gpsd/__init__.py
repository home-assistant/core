"""The GPSD integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .gpsd_client import GPSDClient

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GPSDConfigEntry = ConfigEntry[GPSDClient]


async def async_setup_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Set up GPSD from a config entry."""
    client = GPSDClient()
    entry.runtime_data = client

    def setup() -> None:
        host = entry.data.get(CONF_HOST)
        port = entry.data.get(CONF_PORT)
        client.stream_data(host, port)
        client.run_thread()

    await hass.async_add_executor_job(setup)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data
        client.stream_data(enable=False)

    return unload_ok
