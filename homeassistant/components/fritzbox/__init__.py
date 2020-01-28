"""Support for AVM Fritz!Box smarthome devices."""
from pyfritzhome import Fritzhome
import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SUPPORTED_DOMAINS

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DEVICES): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_HOST): cv.string,
                                vol.Required(CONF_PASSWORD): cv.string,
                                vol.Required(CONF_USERNAME): cv.string,
                            }
                        )
                    ],
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the AVM Fritz!Box integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN][CONF_DEVICES]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the AVM Fritz!Box platforms."""
    fritz = Fritzhome(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    fritz.login()

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = []
    hass.data[DOMAIN].append(fritz)

    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    return True
