"""Middleware to handle forwarded data by a reverse proxy."""
from ipaddress import ip_address
import logging

from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO
from aiohttp.web import HTTPBadRequest, middleware

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# mypy: allow-untyped-defs


@callback
def setup_forwarded(app, trusted_proxies):
    """Create forwarded middleware for the app."""

    @middleware
    async def forwarded_middleware(request, handler):
        """Process forwarded data by a reverse proxy."""
        overrides = {}

        # Handle X-Forwarded-For
        forwarded_for = request.headers.getall(X_FORWARDED_FOR, [])
        if not forwarded_for:
            # No forwarding headers, continue as normal
            return await handler(request)

        # Ensure the IP of the connected peer is trusted
        connected_ip = ip_address(request.transport.get_extra_info("peername")[0])
        if not any(connected_ip in trusted_proxy for trusted_proxy in trusted_proxies):
            # Not trusted, continue as normal
            return await handler(request)

        # Multiple X-Forwarded-For headers
        if len(forwarded_for) > 1:
            _LOGGER.error("Too many headers for X-Forwarded-For", extra=request.headers)
            raise HTTPBadRequest

        # Process IP addresses in the forwarded for header
        forwarded_for = list(reversed(forwarded_for[0].split(",")))
        try:
            forwarded_for = [
                ip_address(addr) for addr in (a.strip() for a in forwarded_for) if addr
            ]
        except ValueError:
            _LOGGER.error(
                "Invalid IP address in X-Forwarded-For header", extra=request.headers
            )
            raise HTTPBadRequest

        # Find the last trusted index in the X-Forwarded-For list
        index = 0
        for forwarded_ip in forwarded_for:
            if any(forwarded_ip in trusted_proxy for trusted_proxy in trusted_proxies):
                index += 1
                continue
            overrides["remote"] = str(forwarded_ip)
            break

        # If all the IP addresses are from trusted networks, take the left-most.
        if "remote" not in overrides:
            index = -1
            overrides["remote"] = str(forwarded_for[-1])

        # Handle X-Forwarded-Proto
        forwarded_proto = list(reversed(request.headers.getall(X_FORWARDED_PROTO, [])))
        if forwarded_proto:
            if len(forwarded_proto) > 1:
                _LOGGER.error(
                    "Too many headers for X_FORWARDED_PROTO header",
                    extra=request.headers,
                )
                raise HTTPBadRequest
            forwarded_proto = forwarded_proto[0].split(",")
            forwarded_proto = [p.strip() for p in forwarded_proto]

            # Ideally this should take the scheme corresponding to the entry
            # in X-Forwarded-For that was chosen, but some proxies (the
            # Kubernetes NGINX ingress, for example) only retain one element
            # in X-Forwarded-Proto. In that case, use what we have.
            if index >= len(forwarded_proto):
                index = -1

            overrides["scheme"] = forwarded_proto[index]

        # Handle X-Forwarded-Host
        forwarded_host = request.headers.getall(X_FORWARDED_HOST, [])
        if forwarded_host:
            # Multiple X-Forwarded-Host headers
            if len(forwarded_host) > 1:
                _LOGGER.error(
                    "Too many headers for X-Forwarded-Host", extra=request.headers
                )
                raise HTTPBadRequest

            overrides["host"] = forwarded_host[0]

        request = request.clone(**overrides)
        return await handler(request)

    app.middlewares.append(forwarded_middleware)
