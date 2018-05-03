"""Helpers to resolve client ID/secret."""
import base64
from functools import wraps
import hmac

import aiohttp.hdrs


def verify_client(method):
    """Decorator to verify client id/secret on requests."""
    @wraps(method)
    async def wrapper(view, request, *args, **kwargs):
        """Verify client id/secret before doing request."""
        client_id = await _verify_client(request)

        if client_id is None:
            return view.json({
                'error': 'invalid_client',
            }, status_code=401)

        return await method(
            view, request, *args, client_id=client_id, **kwargs)

    return wrapper


async def _verify_client(request):
    """Method to verify the client id/secret in consistent time.

    By using a consistent time for looking up client id and comparing the
    secret, we prevent attacks by malicious actors trying different client ids
    and are able to derive from the time it takes to process the request if
    they guessed the client id correctly.
    """
    if aiohttp.hdrs.AUTHORIZATION not in request.headers:
        return None

    auth_type, auth_value = \
        request.headers.get(aiohttp.hdrs.AUTHORIZATION).split(' ', 1)

    if auth_type != 'Basic':
        return None

    decoded = base64.b64decode(auth_value).decode('utf-8')
    try:
        client_id, client_secret = decoded.split(':', 1)
    except ValueError:
        # If no ':' in decoded
        return None

    client = await request.app['hass'].auth.async_get_client(client_id)

    if client is None:
        # Still do a compare so we run same time as if a client was found.
        hmac.compare_digest(client_secret.encode('utf-8'),
                            client_secret.encode('utf-8'))
        return None

    if hmac.compare_digest(client_secret.encode('utf-8'),
                           client.secret.encode('utf-8')):
        return client_id

    return None
