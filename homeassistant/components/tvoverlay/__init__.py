"""The TvOverlay integration."""
from tvoverlay import Notifications
from tvoverlay.exceptions import ConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import DOMAIN

PLATFORMS = [Platform.NOTIFY]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TvOverlay config entry."""
    notifier = Notifications(entry.data[CONF_HOST])
    try:
        await notifier.async_connect()
    except ConnectError as ex:
        raise ConfigEntryNotReady(
            f"Failed to connect to host: {entry.data[CONF_HOST]}"
        ) from ex

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            dict(entry.data),
            {},
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TvOverlay config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
