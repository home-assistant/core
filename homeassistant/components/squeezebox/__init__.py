"""The Logitech Squeezebox integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                MP_DOMAIN: vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_USERNAME): cv.string,
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Logitech Squeezebox component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Logitech Squeezebox from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True
