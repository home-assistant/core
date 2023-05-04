"""Support for Hydrawise cloud."""

from typing import Any

from hydrawiser.core import Hydrawiser
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SCAN_INTERVAL
from .coordinator import HydrawiseDataUpdateCoordinator

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hunter Hydrawise component."""
    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        hydrawise = await hass.async_add_executor_job(Hydrawiser, access_token)
        hass.data[DOMAIN] = HydrawiseDataUpdateCoordinator(
            hass, hydrawise, scan_interval
        )
    except (ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady from ex

    # NOTE: We don't need to call async_config_entry_first_refresh() because
    # data is fetched when the Hydrawiser object is instantiated.

    return True


class HydrawiseHub:
    """Representation of a base Hydrawise device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data
