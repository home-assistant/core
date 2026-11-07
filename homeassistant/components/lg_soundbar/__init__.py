"""The lg_soundbar component."""

from aiotemescal import TemescalClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

PLATFORMS = [Platform.MEDIA_PLAYER]

type LGSoundbarConfigEntry = ConfigEntry[TemescalClient]


async def async_setup_entry(hass: HomeAssistant, entry: LGSoundbarConfigEntry) -> None:
    """Set up platform from a ConfigEntry."""
    client = TemescalClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    entry.runtime_data = client
    entry.async_on_unload(client.stop)

    # Entries are not unloaded when Home Assistant stops
    async def _async_stop(event: Event) -> None:
        await client.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Soundbars are sometimes unplugged, so the client keeps reconnecting in the
    # background instead of failing the setup while the device is unreachable
    await client.start()


async def async_unload_entry(hass: HomeAssistant, entry: LGSoundbarConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
