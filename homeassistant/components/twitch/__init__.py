"""The Twitch component."""

from twitchAPI.twitch import AuthScope

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN = "twitch"

CONF_CHANNELS = "channels"

OAUTH_SCOPES = [AuthScope.USER_READ_SUBSCRIPTIONS]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twitch from a config entry."""

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Twitch config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
