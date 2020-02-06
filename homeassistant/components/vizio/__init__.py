"""The vizio component."""
import voluptuous as vol

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
)


def validate_auth(config):
    """Validate presence of CONF_ACCESS_TOKEN when CONF_DEVICE_CLASS=tv."""
    token = config.get(CONF_ACCESS_TOKEN)
    if config[CONF_DEVICE_CLASS] == "tv" and not token:
        raise vol.Invalid(
            f"When '{CONF_DEVICE_CLASS}' is 'tv' then '{CONF_ACCESS_TOKEN}' is required.",
            path=[CONF_ACCESS_TOKEN],
        )
    return config


VIZIO_SCHEMA = {
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): vol.All(
        cv.string, vol.Lower, vol.In(["tv", "soundbar"])
    ),
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=10)
    ),
}
