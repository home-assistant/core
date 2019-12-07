"""The Google Stackdriver integration."""

import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from google.cloud.logging import Client

from .const import DOMAIN

CONF_KEYFILE = "key_file"
CONF_LABELS = "labels"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_KEYFILE): cv.isfile, vol.Optional(CONF_LABELS): dict}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Google Stackdriver component."""
    sd_config = config[DOMAIN]

    client = Client.from_service_account_json(sd_config[CONF_KEYFILE])
    client.setup_logging(labels=sd_config[CONF_LABELS])
    return True
