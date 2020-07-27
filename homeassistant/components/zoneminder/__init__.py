"""Support for ZoneMinder."""
import logging

import voluptuous as vol
from zoneminder.zm import ZoneMinder

from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

CONF_PATH_ZMS = "path_zms"

DEFAULT_PATH = "/zm/"
DEFAULT_PATH_ZMS = "/zm/cgi-bin/nph-zms"
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True
DOMAIN = "zoneminder"

HOST_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [HOST_CONFIG_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

SERVICE_SET_RUN_STATE = "set_run_state"
SET_RUN_STATE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ID): cv.string, vol.Required(ATTR_NAME): cv.string}
)


def setup(hass, config):
    """Set up the ZoneMinder component."""

    hass.data[DOMAIN] = {}

    success = True

    for conf in config[DOMAIN]:
        protocol = "https" if conf[CONF_SSL] else "http"

        host_name = conf[CONF_HOST]
        server_origin = f"{protocol}://{host_name}"
        zm_client = ZoneMinder(
            server_origin,
            conf.get(CONF_USERNAME),
            conf.get(CONF_PASSWORD),
            conf.get(CONF_PATH),
            conf.get(CONF_PATH_ZMS),
            conf.get(CONF_VERIFY_SSL),
        )
        hass.data[DOMAIN][host_name] = zm_client

        success = zm_client.login() and success

    def set_active_state(call):
        """Set the ZoneMinder run state to the given state name."""
        zm_id = call.data[ATTR_ID]
        state_name = call.data[ATTR_NAME]
        if zm_id not in hass.data[DOMAIN]:
            _LOGGER.error("Invalid ZoneMinder host provided: %s", zm_id)
        if not hass.data[DOMAIN][zm_id].set_active_state(state_name):
            _LOGGER.error(
                "Unable to change ZoneMinder state. Host: %s, state: %s",
                zm_id,
                state_name,
            )

    hass.services.register(
        DOMAIN, SERVICE_SET_RUN_STATE, set_active_state, schema=SET_RUN_STATE_SCHEMA
    )

    hass.async_create_task(
        async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    )

    return success
