"""Middleware to fetch real IP."""

from ipaddress import ip_address

from aiohttp.web import middleware
from aiohttp.hdrs import X_FORWARDED_FOR

from homeassistant.core import callback

from .const import KEY_REAL_IP


@callback
def setup_real_ip(app, use_x_forwarded_for, trusted_networks):
    """Create IP Ban middleware for the app."""
    @middleware
    async def real_ip_middleware(request, handler):
        """Real IP middleware."""
        if (use_x_forwarded_for and
                X_FORWARDED_FOR in request.headers):
            forwarded_for = request.headers.get(X_FORWARDED_FOR).split(', ')
            for ip_addr in forwarded_for:
                if (any(ip_address(ip_addr) in trusted_network
                        for trusted_network in trusted_networks)):
                    continue
                else:
                    request[KEY_REAL_IP] = ip_address(ip_addr)
                    break
            if request.get(KEY_REAL_IP) is None:
                request[KEY_REAL_IP] = ip_address(forwarded_for[0])
        else:
            request[KEY_REAL_IP] = \
                ip_address(request.transport.get_extra_info('peername')[0])

        return await handler(request)

    async def app_startup(app):
        """Initialize bans when app starts up."""
        app.middlewares.append(real_ip_middleware)

    app.on_startup.append(app_startup)
