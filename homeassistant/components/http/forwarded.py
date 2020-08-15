"""Middleware to handle forwarded data by a reverse proxy."""
from ipaddress import ip_address
import logging

from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO
from aiohttp.web import HTTPBadRequest, middleware

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# mypy: allow-untyped-defs


@callback
def async_setup_forwarded(app, trusted_proxies):
    """Create forwarded middleware for the app.

    Process IP addresses, proto and host information in the forwarded for headers.

    `X-Forwarded-For: <client>, <proxy1>, <proxy2>`
    e.g., `X-Forwarded-For: 203.0.113.195, 70.41.3.18, 150.172.238.178`

    We go through the list from the right side, and skip all entries that are in our
    trusted proxies list. The first non-trusted IP is used as the client IP. If all
    items in the X-Forwarded-For are trusted, including the most left item (client),
    the most left item is used. In the latter case, the client connection originated
    from an IP that is also listed as a trusted proxy IP or network.

    `X-Forwarded-Proto: <client>, <proxy1>, <proxy2>`
    e.g., `X-Forwarded-Proto: https, http, http`
    OR `X-Forwarded-Proto: https` (one entry, even with multiple proxies)

    The X-Forwarded-Proto is determined based on the corresponding entry of the
    X-Forwarded-For header that is used/chosen as the client IP. However,
    some proxies, for example, Kubernetes NGINX ingress, only retain one element
    in the X-Forwarded-Proto header. In that case, we'll just use what we have.

    `X-Forwarded-Host: <host>`
    e.g., `X-Forwarded-Host: example.com`

    If the previous headers are processed successfully, and the X-Forwarded-Host is
    present, it will be used.

    Additionally:
      - If no X-Forwarded-For header is found, the processing of all headers is skipped.
      - Log a warning when untrusted connected peer provides X-Forwarded-For headers.
      - If multiple instances of X-Forwarded-For, X-Forwarded-Proto or
        X-Forwarded-Host are found, an HTTP 400 status code is thrown.
      - If malformed or invalid (IP) data in X-Forwarded-For header is found,
        an HTTP 400 status code is thrown.
      - The connected client peer on the socket of the incoming connection,
        must be trusted for any processing to take place.
      - If the number of elements in X-Forwarded-Proto does not equal 1 or
        is equal to the number of elements in X-Forwarded-For, an HTTP 400
        status code is thrown.
      - If an empty X-Forwarded-Host is provided, an HTTP 400 status code is thrown.
      - If an empty X-Forwarded-Proto is provided, or an empty element in the list,
        an HTTP 400 status code is thrown.
    """

    @middleware
    async def forwarded_middleware(request, handler):
        """Process forwarded data by a reverse proxy."""
        overrides = {}

        # Handle X-Forwarded-For
        forwarded_for_headers = request.headers.getall(X_FORWARDED_FOR, [])
        if not forwarded_for_headers:
            # No forwarding headers, continue as normal
            return await handler(request)

        # Ensure the IP of the connected peer is trusted
        connected_ip = ip_address(request.transport.get_extra_info("peername")[0])
        if not any(connected_ip in trusted_proxy for trusted_proxy in trusted_proxies):
            _LOGGER.warning(
                "Received X-Forwarded-For header from untrusted proxy %s, headers not processed",
                connected_ip,
            )
            # Not trusted, continue as normal
            return await handler(request)

        # Multiple X-Forwarded-For headers
        if len(forwarded_for_headers) > 1:
            _LOGGER.error(
                "Too many headers for X-Forwarded-For: %s", forwarded_for_headers
            )
            raise HTTPBadRequest

        # Process X-Forwarded-For from the right side (by reversing the list)
        forwarded_for_split = list(reversed(forwarded_for_headers[0].split(",")))
        try:
            forwarded_for = [ip_address(addr.strip()) for addr in forwarded_for_split]
        except ValueError:
            _LOGGER.error(
                "Invalid IP address in X-Forwarded-For: %s", forwarded_for_headers[0]
            )
            raise HTTPBadRequest

        # Find the last trusted index in the X-Forwarded-For list
        forwarded_for_index = 0
        for forwarded_ip in forwarded_for:
            if any(forwarded_ip in trusted_proxy for trusted_proxy in trusted_proxies):
                forwarded_for_index += 1
                continue
            overrides["remote"] = str(forwarded_ip)
            break
        else:
            # If all the IP addresses are from trusted networks, take the left-most.
            forwarded_for_index = -1
            overrides["remote"] = str(forwarded_for[-1])

        # Handle X-Forwarded-Proto
        forwarded_proto_headers = request.headers.getall(X_FORWARDED_PROTO, [])
        if forwarded_proto_headers:
            if len(forwarded_proto_headers) > 1:
                _LOGGER.error(
                    "Too many headers for X-Forward-Proto: %s", forwarded_proto_headers
                )
                raise HTTPBadRequest

            forwarded_proto_split = list(
                reversed(forwarded_proto_headers[0].split(","))
            )
            forwarded_proto = [proto.strip() for proto in forwarded_proto_split]

            # Catch empty values
            if "" in forwarded_proto:
                _LOGGER.error(
                    "Empty item received in X-Forward-Proto header: %s",
                    forwarded_proto_headers[0],
                )
                raise HTTPBadRequest

            # The X-Forwarded-Proto contains either one element, or the equals number
            # of elements as X-Forwarded-For
            if len(forwarded_proto) not in (1, len(forwarded_for)):
                _LOGGER.error(
                    "Incorrect number of elements in X-Forward-Proto. Expected 1 or %d, got %d: %s",
                    len(forwarded_for),
                    len(forwarded_proto),
                    forwarded_proto_headers[0],
                )
                raise HTTPBadRequest

            # Ideally this should take the scheme corresponding to the entry
            # in X-Forwarded-For that was chosen, but some proxies only retain
            # one element. In that case, use what we have.
            overrides["scheme"] = forwarded_proto[-1]
            if len(forwarded_proto) != 1:
                overrides["scheme"] = forwarded_proto[forwarded_for_index]

        # Handle X-Forwarded-Host
        forwarded_host_headers = request.headers.getall(X_FORWARDED_HOST, [])
        if forwarded_host_headers:
            # Multiple X-Forwarded-Host headers
            if len(forwarded_host_headers) > 1:
                _LOGGER.error(
                    "Too many headers for X-Forwarded-Host: %s", forwarded_host_headers
                )
                raise HTTPBadRequest

            forwarded_host = forwarded_host_headers[0].strip()
            if not forwarded_host:
                _LOGGER.error("Empty value received in X-Forward-Host header")
                raise HTTPBadRequest

            overrides["host"] = forwarded_host

        # Done, create a new request based on gathered data.
        request = request.clone(**overrides)
        return await handler(request)

    app.middlewares.append(forwarded_middleware)
