"""Constants."""

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv

DOMAIN = "sky_remote"
CONF_LEGACY_CONTROL_PORT = "legacy_port"
SKY_REMOTE_CONFIG_SCHEMA = {
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_LEGACY_CONTROL_PORT, default=False): cv.boolean,
}
