"""Local Nest authentication."""
from functools import partial

from aiohttp.client_exceptions import ClientError

from homeassistant.core import callback
from . import config_flow
from .const import DOMAIN

ACCESS_TOKEN_URL = 'https://api.home.nest.com/oauth2/access_token'
AUTHORIZE_URL = 'https://home.nest.com/login/oauth2?client_id={}&state={}'


@callback
def initialize(hass, client_id, client_secret):
    """Initialize a local auth provider."""
    config_flow.register_flow_implementation(
        hass, DOMAIN, 'local', partial(generate_auth_url, client_id),
        partial(resolve_auth_code, hass, client_id, client_secret)
    )


async def generate_auth_url(client_id, flow_id):
    """Generate an authorize url."""
    return AUTHORIZE_URL.format(client_id, flow_id)


async def resolve_auth_code(hass, client_id, client_secret, code):
    """Resolve an authorization code."""
    session = hass.helpers.aiohttp_client.async_get_clientsession()

    try:
        res = await session.post(ACCESS_TOKEN_URL, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code'
        })
        if res.status == 401:
            raise config_flow.CodeInvalid()

        return await res.json()
    except ClientError:
        raise config_flow.NestAuthError('Unknown error: {}'.format(res.status))
