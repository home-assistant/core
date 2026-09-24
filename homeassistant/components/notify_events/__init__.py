"""The notify_events component."""

import probatio

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.Schema({probatio.Required(CONF_TOKEN): cv.string})},
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the notify_events component."""

    hass.data[DOMAIN] = config[DOMAIN]
    discovery.load_platform(hass, Platform.NOTIFY, DOMAIN, {}, config)
    return True
