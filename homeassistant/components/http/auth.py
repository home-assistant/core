"""Authentication for HTTP component."""
import asyncio
import base64
import hmac
import logging

from aiohttp import hdrs
from aiohttp.web import middleware

from homeassistant.const import HTTP_HEADER_HA_AUTH
from .util import get_real_ip
from .const import KEY_TRUSTED_NETWORKS, KEY_AUTHENTICATED

DATA_API_PASSWORD = 'api_password'

_LOGGER = logging.getLogger(__name__)


REQUIREMENTS = ['aiohttp_session==1.2.1',  # Update to vn2 when >=python3.5
                'cryptography==2.1.4']


@middleware
@asyncio.coroutine
def auth_middleware(request, handler):
    """Authenticate as middleware."""
    # If no password set, just always set authenticated=True
    if request.app['hass'].http.api_password is None:
        request[KEY_AUTHENTICATED] = True
        return (yield from handler(request))

    # Check authentication
    authenticated = False

    session = yield from get_session(request)

    if session.get(KEY_AUTHENTICATED, False):
        authenticated = True

    elif (HTTP_HEADER_HA_AUTH in request.headers and
          validate_password(request, request.headers[HTTP_HEADER_HA_AUTH])):
        # A valid auth header has been set
        authenticated = True

    elif (DATA_API_PASSWORD in request.query and
          validate_password(request, request.query[DATA_API_PASSWORD])):
        authenticated = True

    elif (hdrs.AUTHORIZATION in request.headers and
          validate_authorization_header(request)):
        authenticated = True

    elif is_trusted_ip(request):
        authenticated = True

    request[KEY_AUTHENTICATED] = authenticated

    # Store whether we are authenticated in the session so that
    # future requests don't require credentials to authenticate.
    session[KEY_AUTHENTICATED] = authenticated

    return (yield from handler(request))


@asyncio.coroutine
def get_session(request):
    """Get a dictionary for the current session."""
    from aiohttp_session import get_session as aio_get_session
    return (yield from aio_get_session(request))


def session_middleware_factory():
    """Construct a aiohttp-session middleware instance."""
    # Note: Because the secret key is generated on-the-fly, the session
    # cookie will only be valid for the lifetime of the hass server.
    # Is is feasible to make the secret_key a configuration item, should
    # we want to persist session data.
    from cryptography import fernet
    from aiohttp_session.cookie_storage import EncryptedCookieStorage
    from aiohttp_session import session_middleware

    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)

    return session_middleware(EncryptedCookieStorage(secret_key))


def is_trusted_ip(request):
    """Test if request is from a trusted ip."""
    ip_addr = get_real_ip(request)

    return ip_addr and any(
        ip_addr in trusted_network for trusted_network
        in request.app[KEY_TRUSTED_NETWORKS])


def validate_password(request, api_password):
    """Test if password is valid."""
    return hmac.compare_digest(
        api_password, request.app['hass'].http.api_password)


def validate_authorization_header(request):
    """Test an authorization header if valid password."""
    if hdrs.AUTHORIZATION not in request.headers:
        return False

    auth_type, auth = request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)

    if auth_type != 'Basic':
        return False

    decoded = base64.b64decode(auth).decode('utf-8')
    username, password = decoded.split(':', 1)

    if username != 'homeassistant':
        return False

    return validate_password(request, password)
