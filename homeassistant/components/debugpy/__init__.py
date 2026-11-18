"""The Remote Python Debugger integration."""

import probatio

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_START, CONF_WAIT, DATA_DEBUGPY_CONFIG, DOMAIN
from .helpers import async_start_debugger
from .services import async_setup_services

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(CONF_HOST, default="0.0.0.0"): cv.string,
                probatio.Optional(CONF_PORT, default=5678): probatio.Port(),
                probatio.Optional(CONF_START, default=True): cv.boolean,
                probatio.Optional(CONF_WAIT, default=False): cv.boolean,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remote Python Debugger component."""
    conf = config[DOMAIN]
    hass.data[DATA_DEBUGPY_CONFIG] = conf

    async_setup_services(hass)

    # If set to start the debugger on startup, do so
    if conf[CONF_START]:
        await async_start_debugger(hass)

    return True
