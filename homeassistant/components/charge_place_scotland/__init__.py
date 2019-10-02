"""Support for getting information from thingsmobile account."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "charge_place_scotland"

TIMEOUT = 5

_api_base_url = "https://map.chargeplacescotland.org/api/{}"


async def async_setup(hass, config):
    """
    Set up CPS sensors.

    This could be simplified - but I'm going to expand this in the future
    """

    hass.data[DOMAIN] = {"base_url": _api_base_url}
    return True
