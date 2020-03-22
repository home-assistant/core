"""The Google Cloud Logging integration."""

import logging

from google.cloud.logging import Client
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

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

DOMAIN = "google_cloud_logging"

CONF_KEY_FILE = "key_file"
CONF_LEVEL = "level"
CONF_LABELS = "labels"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_KEY_FILE): cv.isfile,
                vol.Optional(CONF_LEVEL, default="info"): _VALID_LOG_LEVEL,
                vol.Optional(CONF_LABELS): dict,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Google Cloud Logging integration."""
    sd_config = config[DOMAIN]
    try:
        client = Client.from_service_account_json(sd_config[CONF_KEY_FILE])
    except ValueError as error:
        _LOGGER.warning("Failed to load credentials: %s", error)
        return False
    client.setup_logging(
        log_level=sd_config[CONF_LEVEL], labels=sd_config.get(CONF_LABELS, {})
    )
    return True
