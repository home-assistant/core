"""Local Nest authentication."""
import asyncio
from functools import partial

from homeassistant.core import callback
from . import config_flow
from .const import DOMAIN


@callback
def initialize(hass, client_id, client_secret):
    """Initialize a local auth provider."""
    config_flow.register_flow_implementation(
        hass, DOMAIN, 'local', partial(generate_auth_url, client_id),
        partial(resolve_auth_code, hass, client_id, client_secret)
    )


async def generate_auth_url(client_id, flow_id):
    """Generate an authorize url."""
    from nest.nest import AUTHORIZE_URL
    return AUTHORIZE_URL.format(client_id, flow_id)


async def resolve_auth_code(hass, client_id, client_secret, code):
    """Resolve an authorization code."""
    from nest.nest import NestAuth, AuthorizationError

    result = asyncio.Future()
    auth = NestAuth(
        client_id=client_id,
        client_secret=client_secret,
        auth_callback=result.set_result,
    )
    auth.pin = code

    try:
        await hass.async_add_job(auth.login)
        return await result
    except AuthorizationError as err:
        if err.response.status_code == 401:
            raise config_flow.CodeInvalid()
        else:
            raise config_flow.NestAuthError('Unknown error: {} ({})'.format(
                err, err.response.status_code))
