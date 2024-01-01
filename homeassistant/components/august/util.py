"""August util functions."""

import socket

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client


@callback
def async_create_august_clientsession(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Create an aiohttp session for the august integration."""
    # Create an aiohttp session instead of using the default one since the
    # default one is likely to trigger august's WAF if another integration
    # is also using Cloudflare
    #
    # The family is set to AF_INET because IPv6 keeps coming up as an issue
    # see https://github.com/home-assistant/core/issues/97146
    #
    # When https://github.com/aio-libs/aiohttp/issues/4451 is implemented
    # we can allow IPv6 again
    #
    return aiohttp_client.async_create_clientsession(hass, family=socket.AF_INET)
