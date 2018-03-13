"""Middleware to fetch real IP."""

from ipaddress import ip_address

from aiohttp.web import middleware
from aiohttp.hdrs import X_FORWARDED_FOR

from homeassistant.core import callback

from .const import KEY_REAL_IP


@callback
def setup_real_ip(app, use_x_forwarded_for):
    """Create IP Ban middleware for the app."""
    @middleware
    async def real_ip_middleware(request, handler):
        """Real IP middleware."""
        if (use_x_forwarded_for and
                X_FORWARDED_FOR in request.headers):
            request[KEY_REAL_IP] = ip_address(
                request.headers.get(X_FORWARDED_FOR).split(',')[0])
        else:
            request[KEY_REAL_IP] = \
                ip_address(request.transport.get_extra_info('peername')[0])

        return await handler(request)

    async def app_startup(app):
        """Initialize bans when app starts up."""
        app.middlewares.append(real_ip_middleware)

    app.on_startup.append(app_startup)
