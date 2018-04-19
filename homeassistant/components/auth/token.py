"""Token related helpers for the auth component."""
TEMP_SECRET = 'supersecret'

from homeassistant.core import callback
from homeassistant.util import dt as dt_util


@callback
def async_refresh_token(hass, token):
    """Generate a set of access/refresh tokens for a user.

    Refresh token data:
    typ: token type, refresh.
    sub: identifier of the user.
    aud: id of client requesting token on behalf of user.
    iat: unix timestamp when token was issued.
    """
    import jwt

    claims = {
        'id': token.id,
        'typ': 'refresh',
        'sub': token.user.id,
        'aud': token.client_id,
        'iat': int(dt_util.utcnow().timestamp())
    }

    return jwt.encode(
        claims, TEMP_SECRET, algorithm='HS256').decode('utf-8')


@callback
def async_access_token(hass, token):
    """Generate an access token for a user.

    Access token data:
    typ: token type, access.
    sub: identifier of the user.
    aud: id of client requesting token on behalf of user.
    auth_time: unix timestamp the refresh token was granted.
    iat: unix timestsamp when token was issued.
    exp: unix timestamp when token expires.
    """
    import jwt

    return jwt.encode({
        'id': token.id,
        'typ': 'access',
        'sub': token.user.id,
        'aud': token.client_id,
        'auth_time': int(token.created_at.timestamp()),
        'iat': int(dt_util.utcnow().timestamp()),
        'exp': int((dt_util.utcnow() + token.access_token_valid).timestamp()),
    }, TEMP_SECRET, algorithm='HS256').decode('utf-8')


async def async_resolve_token(hass, token, client_id=None):
    """Get User and AuthToken from a JWT token.

    Return None if token cannot be validated.
    """
    import jwt

    options = {}
    if client_id is None:
        options['verify_aud'] = False

    try:
        claims = jwt.decode(token, TEMP_SECRET, audience=client_id,
                            options=options)
    except jwt.exceptions.InvalidTokenError:
        return None

    # Fetch the user and see if exists and is active
    user = await hass.auth.async_get_user(claims['sub'])
    if user is None or not user.is_active:
        return None

    # Ensure token still exists.
    for token in user.tokens:
        if token.id == claims['id']:
            break
    else:
        # No token found
        return None

    return {
        'user': user,
        'token': token,
    }
