"""Common code for GogoGate2 component."""
import logging

from pygogogate2 import Gogogate2API

from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def get_api(config_data: dict) -> Gogogate2API:
    """Get an api object for config data."""
    return Gogogate2API(
        config_data[CONF_USERNAME],
        config_data[CONF_PASSWORD],
        config_data[CONF_IP_ADDRESS],
    )


async def async_can_connect(hass: HomeAssistant, api: Gogogate2API) -> bool:
    """Check if the device is accessible."""
    try:
        devices = await hass.async_add_executor_job(api.get_devices)
        if devices is False:
            return False

    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to connect")
        return False

    return True
