"""Cloud APIs."""
from functools import wraps
import logging

from . import auth_api

_LOGGER = logging.getLogger(__name__)


def _check_token(func):
    """Decorate a function to verify valid token."""
    @wraps(func)
    async def check_token(cloud, *args):
        """Validate token, then call func."""
        await cloud.hass.async_add_executor_job(auth_api.check_token, cloud)
        return await func(cloud, *args)

    return check_token


def _log_response(func):
    """Decorate a function to log bad responses."""
    @wraps(func)
    async def log_response(*args):
        """Log response if it's bad."""
        resp = await func(*args)
        meth = _LOGGER.debug if resp.status < 400 else _LOGGER.warning
        meth('Fetched %s (%s)', resp.url, resp.status)
        return resp

    return log_response


@_check_token
@_log_response
async def async_create_cloudhook(cloud):
    """Create a cloudhook."""
    websession = cloud.hass.helpers.aiohttp_client.async_get_clientsession()
    return await websession.post(
        cloud.cloudhook_create_url, headers={
            'authorization': cloud.id_token
        })
