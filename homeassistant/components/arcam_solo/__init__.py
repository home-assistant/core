"""The Arcam Solo integration."""

from pyarcamsolo import ArcamSolo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type ArcamSoloConfigEntry = ConfigEntry[ArcamSolo]


async def async_setup_entry(hass: HomeAssistant, entry: ArcamSoloConfigEntry) -> bool:
    """Set up Arcam Solo from a config entry."""

    entry.runtime_data = ArcamSolo(uri=entry.data[CONF_DEVICE])
    try:
        await entry.runtime_data.connect()
    except (TimeoutError, OSError) as err:
        raise ConfigEntryNotReady("cannot connect to device.") from err
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArcamSoloConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.disconnect()
    return unload_ok
