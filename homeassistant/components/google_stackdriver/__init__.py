"""The Google Stackdriver integration."""

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from google.cloud.logging import Client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

LOGSEVERITY = {
    "CRITICAL": 50,
    "FATAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "WARN": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(LOGSEVERITY))


CONF_KEYFILE = "key_file"
CONF_LEVEL = "level"
CONF_LABELS = "labels"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_KEYFILE): cv.isfile,
                vol.Optional(CONF_LEVEL, default="info"): _VALID_LOG_LEVEL,
                vol.Optional(CONF_LABELS): dict,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Google Stackdriver component."""
    sd_config = config[DOMAIN]
    try:
        client = Client.from_service_account_json(sd_config[CONF_KEYFILE])
    except ValueError as e:
        _LOGGER.warning("Failed to load credentials: %s", e)
        return False
    client.setup_logging(
        log_level=sd_config[CONF_LEVEL], labels=sd_config.get(CONF_LABELS, {})
    )
    return True
