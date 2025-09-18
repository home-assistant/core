"""Helpers to resolve client ID/secret."""

from __future__ import annotations

from html.parser import HTMLParser
from ipaddress import ip_address
import logging
from urllib.parse import ParseResult, urljoin, urlparse

import aiohttp
import aiohttp.client_exceptions

from homeassistant.core import HomeAssistant
from homeassistant.util.network import is_local

_LOGGER = logging.getLogger(__name__)


async def verify_redirect_uri(
    hass: HomeAssistant, client_id: str, redirect_uri: str
) -> bool:
    """Verify that the client and redirect uri match."""
    try:
        client_id_parts = _parse_client_id(client_id)
    except ValueError:
        return False

    redirect_parts = _parse_url(redirect_uri)

    # Verify redirect url and client url have same scheme and domain.
    is_valid = (
        client_id_parts.scheme == redirect_parts.scheme
        and client_id_parts.netloc == redirect_parts.netloc
    )

    if is_valid:
        return True

    # Whitelist the iOS and Android callbacks so that people can link apps
    # without being connected to the internet.
    if (
        client_id == "https://home-assistant.io/iOS"
        and redirect_uri == "homeassistant://auth-callback"
    ):
        return True

    if client_id == "https://home-assistant.io/android" and redirect_uri in (
        "homeassistant://auth-callback",
        "https://wear.googleapis.com/3p_auth/io.homeassistant.companion.android",
        "https://wear.googleapis-cn.com/3p_auth/io.homeassistant.companion.android",
    ):
        return True

    # IndieAuth 4.2.2 allows for redirect_uri to be on different domain
    # but needs to be specified in link tag when fetching `client_id`.
    redirect_uris = await fetch_redirect_uris(hass, client_id)
    return redirect_uri in redirect_uris


class LinkTagParser(HTMLParser):
    """Parser to find link tags."""

    def __init__(self, rel: str) -> None:
        """Initialize a link tag parser."""
        super().__init__()
        self.rel = rel
        self.found: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle finding a start tag."""
        if tag != "link":
            return

        attributes: dict[str, str | None] = dict(attrs)

        if attributes.get("rel") == self.rel:
            self.found.append(attributes.get("href"))


async def fetch_redirect_uris(hass: HomeAssistant, url: str) -> list[str]:
    """Find link tag with redirect_uri values.

    IndieAuth 4.2.2

    The client SHOULD publish one or more <link> tags or Link HTTP headers with
    a rel attribute of redirect_uri at the client_id URL.

    We limit to the first 10kB of the page.

    We do not implement extracting redirect uris from headers.
    """
    parser = LinkTagParser("redirect_uri")
    chunks = 0
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp,
        ):
            async for data in resp.content.iter_chunked(1024):
                parser.feed(data.decode())
                chunks += 1

                if chunks == 10:
                    break

    except TimeoutError:
        _LOGGER.error("Timeout while looking up redirect_uri %s", url)
    except aiohttp.client_exceptions.ClientSSLError:
        _LOGGER.error("SSL error while looking up redirect_uri %s", url)
    except aiohttp.client_exceptions.ClientOSError as ex:
        _LOGGER.error("OS error while looking up redirect_uri %s: %s", url, ex.strerror)
    except aiohttp.client_exceptions.ClientConnectionError:
        _LOGGER.error(
            "Low level connection error while looking up redirect_uri %s", url
        )
    except aiohttp.client_exceptions.ClientError:
        _LOGGER.error("Unknown error while looking up redirect_uri %s", url)

    # Authorization endpoints verifying that a redirect_uri is allowed for use
    # by a client MUST look for an exact match of the given redirect_uri in the
    # request against the list of redirect_uris discovered after resolving any
    # relative URLs.
    return [urljoin(url, found) for found in parser.found]


def verify_client_id(client_id: str) -> bool:
    """Verify that the client id is valid."""
    try:
        _parse_client_id(client_id)
    except ValueError:
        return False
    return True


def _parse_url(url: str) -> ParseResult:
    """Parse a url in parts and canonicalize according to IndieAuth."""
    parts = urlparse(url)

    # Canonicalize a url according to IndieAuth 3.2.

    # SHOULD convert the hostname to lowercase
    parts = parts._replace(netloc=parts.netloc.lower())

    # If a URL with no path component is ever encountered,
    # it MUST be treated as if it had the path /.
    if parts.path == "":
        parts = parts._replace(path="/")

    return parts


def _parse_client_id(client_id: str) -> ParseResult:
    """Test if client id is a valid URL according to IndieAuth section 3.2.

    https://indieauth.spec.indieweb.org/#client-identifier
    """
    parts = _parse_url(client_id)

    # Client identifier URLs
    # MUST have either an https or http scheme
    if parts.scheme not in ("http", "https"):
        raise ValueError

    # MUST contain a path component
    # Handled by url canonicalization.

    # MUST NOT contain single-dot or double-dot path segments
    if any(segment in (".", "..") for segment in parts.path.split("/")):
        raise ValueError(
            "Client ID cannot contain single-dot or double-dot path segments"
        )

    # MUST NOT contain a fragment component
    if parts.fragment != "":
        raise ValueError("Client ID cannot contain a fragment")

    # MUST NOT contain a username or password component
    if parts.username is not None:
        raise ValueError("Client ID cannot contain username")

    if parts.password is not None:
        raise ValueError("Client ID cannot contain password")

    # MAY contain a port
    try:
        # parts raises ValueError when port cannot be parsed as int
        _ = parts.port
    except ValueError as ex:
        raise ValueError("Client ID contains invalid port") from ex

    # Additionally, hostnames
    # MUST be domain names or a loopback interface and
    # MUST NOT be IPv4 or IPv6 addresses except for IPv4 127.0.0.1
    # or IPv6 [::1]

    # We are not goint to follow the spec here. We are going to allow
    # any internal network IP to be used inside a client id.

    address = None

    try:
        netloc = parts.netloc

        # Strip the [, ] from ipv6 addresses before parsing
        if netloc[0] == "[" and netloc[-1] == "]":
            netloc = netloc[1:-1]

        address = ip_address(netloc)
    except ValueError:
        # Not an ip address
        pass

    if address is None or is_local(address):
        return parts

    raise ValueError("Hostname should be a domain name or local IP address")
