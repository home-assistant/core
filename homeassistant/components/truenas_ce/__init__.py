"""The TrueNAS integration."""

from aiotruenas import TrueNASClient

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant

from .coordinator import TrueNASConfigEntry, TrueNASCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TrueNASConfigEntry) -> None:
    """Set up TrueNAS from a config entry."""
    client = TrueNASClient(
        entry.data[CONF_HOST],
        entry.data[CONF_API_KEY],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    # Also runs when the setup below fails, so the connection is never leaked.
    entry.async_on_unload(client.close)

    coordinator = TrueNASCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TrueNASConfigEntry) -> None:
    """Unload a TrueNAS config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
