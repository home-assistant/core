"""Get the local IP address of the Home Assistant instance."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

DOMAIN = "local_ip"
PLATFORM = "sensor"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_NAME, default=DOMAIN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up local_ip from configuration.yaml."""
    conf = config.get(DOMAIN)
    if conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, data=conf, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up local_ip from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, PLATFORM)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, PLATFORM)
