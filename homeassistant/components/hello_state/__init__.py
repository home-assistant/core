"""Home Assistant custom component setup module.

This package provides the setup function used to initialize the integration.
"""

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "hello_state"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:  # noqa: D103
    hass.states.set("hello_state.world", "Paulus")
    # Return boolean to indicate that initialization was successful.
    return True
