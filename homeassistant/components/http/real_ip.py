"""Middleware to fetch real IP."""
from ipaddress import ip_address

from aiohttp.hdrs import X_FORWARDED_FOR
from aiohttp.web import middleware

from homeassistant.core import callback

from .const import KEY_REAL_IP


@callback
def setup_real_ip(app, use_x_forwarded_for, trusted_proxies):
    """Create IP Ban middleware for the app."""
    @middleware
    async def real_ip_middleware(request, handler):
        """Real IP middleware."""
        connected_ip = ip_address(
            request.transport.get_extra_info('peername')[0])
        request[KEY_REAL_IP] = connected_ip

        # Only use the XFF header if enabled, present, and from a trusted proxy
        try:
            if (use_x_forwarded_for and
                    X_FORWARDED_FOR in request.headers and
                    any(connected_ip in trusted_proxy
                        for trusted_proxy in trusted_proxies)):
                request[KEY_REAL_IP] = ip_address(
                    request.headers.get(X_FORWARDED_FOR).split(', ')[-1])
        except ValueError:
            pass

        return await handler(request)

    app.middlewares.append(real_ip_middleware)
