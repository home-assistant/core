"""Helpers to resolve client ID/secret."""
from functools import wraps

import aiohttp.hdrs

from homeassistant.core import callback


@callback
def verify_client(request):
    """Decorator to verify the client id/secret in a time safe manner."""
    return 'fake-client-id'  # TEMP

    # Verify client_id, secret
    if aiohttp.hdrs.AUTHORIZATION not in request.headers:
        return False

    auth_type, auth_value = \
        request.headers.get(aiohttp.hdrs.AUTHORIZATION).split(' ', 1)

    if auth_type != 'Basic':
        return False

    # decoded = base64.b64decode(auth_value).decode('utf-8')
    # client_id, client_secret = decoded.split(':', 1)
    # hass = request.app['hass']
    # Use hmac.compare_digest(client_secret, client.secret)

    # Look up client id, compare client secret.
    # secure_lookup should always run in same time wheter it finds or not
    # finds a matching client.
    # client = hass.auth.async_secure_lookup_client(client_id)
    # if we don't find a client, we should still compare passed client
    # secret to itself to spend the same amount of time as a correct
    # request.


def VerifyClient(method):
    """Decorator to verify client id/secret on requests."""
    @wraps(method)
    async def wrapper(view, request, *args, **kwargs):
        """Verify client id/secret before doing request."""
        client_id = verify_client(request)

        if client_id is None:
            return view.json({
                'error': 'invalid_client',
            }, status_code=401)

        return await method(
            view, request, *args, client_id=client_id, **kwargs)

    return wrapper
