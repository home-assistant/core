"""Cloud APIs."""
from functools import wraps

from . import auth_api


def _check_token(func):
    """Decorate a function to verify valid token."""
    @wraps(func)
    async def check_token(cloud, *args):
        """Validate token, then call func."""
        await cloud.hass.async_add_executor_job(auth_api.check_token, cloud)
        return await func(cloud, *args)

    return check_token


@_check_token
async def async_create_cloudhook(cloud, webhook_id):
    """Create a cloudhook."""
    websession = cloud.hass.helpers.aiohttp_client.async_get_clientsession()
    return await websession.post(
        cloud.cloudhook_create_url, headers={
            'authorization': cloud.id_token
        }, json={
            'webhook_id': webhook_id
        })
