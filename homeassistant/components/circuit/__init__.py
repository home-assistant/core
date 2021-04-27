"""The Unify Circuit component."""
import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.helpers import config_validation as cv, discovery

DOMAIN = "circuit"
CONF_WEBHOOK = "webhook"

WEBHOOK_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_URL): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_WEBHOOK): vol.All(cv.ensure_list, [WEBHOOK_SCHEMA])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Unify Circuit component."""
    webhooks = config[DOMAIN][CONF_WEBHOOK]

    for webhook_conf in webhooks:
        hass.async_create_task(
            discovery.async_load_platform(hass, "notify", DOMAIN, webhook_conf, config)
        )

    return True
