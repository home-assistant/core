"""The soundtouch component."""

from typing import TYPE_CHECKING

from libsoundtouch import soundtouch_device
from libsoundtouch.device import SoundTouchDevice
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services

if TYPE_CHECKING:
    from .media_player import SoundTouchMediaPlayer

type SoundTouchConfigEntry = ConfigEntry[SoundTouchData]


PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class SoundTouchData:
    """SoundTouch data stored in the config entry runtime data."""

    def __init__(self, device: SoundTouchDevice) -> None:
        """Initialize the SoundTouch data object for a device."""
        self.device = device
        self.media_player: SoundTouchMediaPlayer | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Bose SoundTouch component."""

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SoundTouchConfigEntry) -> bool:
    """Set up Bose SoundTouch from a config entry."""
    try:
        device = await hass.async_add_executor_job(
            soundtouch_device, entry.data[CONF_HOST]
        )
    except requests.exceptions.ConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to SoundTouch device at {entry.data[CONF_HOST]}"
        ) from err

    entry.runtime_data = SoundTouchData(device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SoundTouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
