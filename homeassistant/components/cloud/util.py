"""Cloud util functions."""
import socket

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client


@callback
def async_create_cloud_clientsession(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Create an aiohttp session for the cloud integration."""
    # Create an aiohttp session instead of using the default one since the
    # default one giving some users with bad network problems.
    # Currently the workaround is to disable IPv6 for the instance.
    # This custom client session, forces the use of IPv4.
    #
    # More context of the situation https://github.com/aio-libs/aiohttp/issues/3620#issuecomment-559870244
    # This can be removed when https://github.com/aio-libs/aiohttp/issues/4451 is implemented.
    #
    return aiohttp_client.async_create_clientsession(hass, family=socket.AF_INET)
