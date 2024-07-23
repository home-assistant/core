"""Support for The Things network."""

import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

CONF_ACCESS_KEY = "access_key"
CONF_APP_ID = "app_id"

DATA_TTN = "data_thethingsnetwork"
DOMAIN = "thethingsnetwork"

TTN_ACCESS_KEY = "ttn_access_key"
TTN_APP_ID = "ttn_app_id"
TTN_DATA_STORAGE_URL = (
    "https://{app_id}.data.thethingsnetwork.org/{endpoint}/{device_id}"
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_APP_ID): cv.string,
                vol.Required(CONF_ACCESS_KEY): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize of The Things Network component."""
    conf = config[DOMAIN]
    app_id = conf.get(CONF_APP_ID)
    access_key = conf.get(CONF_ACCESS_KEY)

    hass.data[DATA_TTN] = {TTN_ACCESS_KEY: access_key, TTN_APP_ID: app_id}

    return True
