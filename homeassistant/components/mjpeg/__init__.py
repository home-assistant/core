"""The MJPEG IP Camera integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .camera import MjpegCamera
from .const import CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, PLATFORMS
from .util import filter_urllib3_logging

__all__ = [
    "CONF_MJPEG_URL",
    "CONF_STILL_IMAGE_URL",
    "MjpegCamera",
    "filter_urllib3_logging",
]


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MJPEG IP Camera integration."""
    filter_urllib3_logging()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
