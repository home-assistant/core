"""The Microsoft Text-to-Speech integration."""

from pycsspeechtts import pycsspeechtts
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_REGION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN
from .helpers import is_unauthorized

PLATFORMS = [Platform.TTS]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Microsoft Text-to-Speech from a config entry."""
    try:
        await hass.async_add_executor_job(
            pycsspeechtts.TTSTranslator,
            entry.data[CONF_API_KEY],
            entry.data[CONF_REGION],
        )
    except RequestException as err:
        if is_unauthorized(err):
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="invalid_api_key"
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
