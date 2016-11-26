"""Authentication for HTTP component."""
import asyncio
import hmac
import logging

from homeassistant.const import HTTP_HEADER_HA_AUTH
from .util import get_real_ip
from .const import KEY_TRUSTED_NETWORKS, KEY_AUTHENTICATED

DATA_API_PASSWORD = 'api_password'

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def auth_middleware(app, handler):
    """Authentication middleware."""
    # If no password set, just always set authenticated=True
    if app['hass'].http.api_password is None:
        @asyncio.coroutine
        def no_auth_middleware_handler(request):
            """Auth middleware to approve all requests."""
            request[KEY_AUTHENTICATED] = True
            return handler(request)

        return no_auth_middleware_handler

    @asyncio.coroutine
    def auth_middleware_handler(request):
        """Auth middleware to check authentication."""
        hass = app['hass']

        # Auth code verbose on purpose
        authenticated = False

        if hmac.compare_digest(request.headers.get(HTTP_HEADER_HA_AUTH, ''),
                               hass.http.api_password):
            # A valid auth header has been set
            authenticated = True

        elif hmac.compare_digest(request.GET.get(DATA_API_PASSWORD, ''),
                                 hass.http.api_password):
            authenticated = True

        elif is_trusted_ip(request):
            authenticated = True

        request[KEY_AUTHENTICATED] = authenticated

        return handler(request)

    return auth_middleware_handler


def is_trusted_ip(request):
    """Test if request is from a trusted ip."""
    ip_addr = get_real_ip(request)

    return ip_addr and any(
        ip_addr in trusted_network for trusted_network
        in request.app[KEY_TRUSTED_NETWORKS])
