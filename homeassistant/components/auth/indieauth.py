"""Helpers to resolve client ID/secret."""

from html.parser import HTMLParser
from http import HTTPStatus
from ipaddress import ip_address
import json
import logging
from typing import override
from urllib.parse import ParseResult, urljoin, urlparse

import aiohttp
import aiohttp.client_exceptions

from homeassistant.core import HomeAssistant
from homeassistant.util.network import is_local

_LOGGER = logging.getLogger(__name__)

# We limit reads of a client_id page to the first 10kB.
MAX_FETCH_BYTES = 10240


async def verify_redirect_uri(
    hass: HomeAssistant, client_id: str, redirect_uri: str
) -> bool:
    """Verify that the client and redirect uri match."""
    try:
        client_id_parts = _parse_client_id(client_id)
    except ValueError:
        return False

    try:
        redirect_parts = _parse_url(redirect_uri)
    except ValueError:
        # A malformed redirect_uri (e.g. an unbalanced IPv6 bracket) must fail
        # validation, not raise into the login flow.
        return False

    # Verify redirect url and client url have same scheme and domain.
    is_valid = (
        client_id_parts.scheme == redirect_parts.scheme
        and client_id_parts.netloc == redirect_parts.netloc
    )

    # Deliberate deviations from a strict OAuth/CIMD reading, kept for
    # compatibility with IndieAuth clients and Home Assistant's own frontend
    # login (which uses the instance URL as client_id with a same-origin
    # redirect_uri):
    # - A same-origin redirect_uri is accepted without registration or a
    #   document fetch.
    # - The client_id page may be fetched from private/local addresses;
    #   local clients are first-class in Home Assistant (see
    #   _parse_client_id).
    # - Redirects are followed when fetching the client_id page for link
    #   tags; a metadata document reached via a redirect is rejected.
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
    if redirect_uri in redirect_uris:
        return True
    if redirect_uris:
        # The client's document/page was fine; the requested redirect_uri just
        # is not registered. Without this the most common misconfiguration
        # (typo, trailing slash, scheme mismatch) is undiagnosable server-side.
        _LOGGER.debug(
            "redirect_uri %s is not among the advertised redirect uris %s for"
            " client_id %s",
            redirect_uri,
            redirect_uris,
            client_id,
        )
    return False


class LinkTagParser(HTMLParser):
    """Parser to find link tags."""

    def __init__(self, rel: str) -> None:
        """Initialize a link tag parser."""
        super().__init__()
        self.rel = rel
        self.found: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle finding a start tag."""
        if tag != "link":
            return

        attributes: dict[str, str | None] = dict(attrs)

        # Skip tags with a missing or empty href: urljoin resolves those to
        # the client_id URL itself instead of naming a redirect target.
        if attributes.get("rel") == self.rel and (href := attributes.get("href")):
            self.found.append(href)


def _reject_json_constant(constant: str) -> None:
    """Reject NaN/Infinity/-Infinity, which RFC 8259 does not allow."""
    raise ValueError(f"Invalid JSON constant: {constant}")


def _is_valid_metadata_client_id(url: str) -> bool:
    """Validate a client_id URL for the metadata-document fallback.

    The client identifier URL must be https with a path component and no
    fragment (a bare trailing # counts as a fragment component). The remaining
    client identifier rules are enforced upstream by _parse_client_id.
    """
    try:
        parts = urlparse(url)
        # urlparse defers port validation until the attribute is accessed.
        _ = parts.port
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.path) and "#" not in url


def _is_valid_metadata_redirect_uri(redirect_uri: str) -> bool:
    """Validate a client ID metadata document redirect_uris entry.

    Entries must be absolute, fragment-free URIs: a non-empty scheme (so
    private-use schemes like app:/callback stay valid) and no fragment per
    RFC 6749 3.1.2 (a bare trailing # counts as a fragment component). An
    unparsable entry (e.g. an unbalanced IPv6 bracket) invalidates the entry
    rather than raising into the login flow.
    """
    try:
        parts = urlparse(redirect_uri)
        # urlparse defers port validation until the attribute is accessed.
        _ = parts.port
    except ValueError:
        return False
    return bool(parts.scheme) and "#" not in redirect_uri


async def fetch_redirect_uris(hass: HomeAssistant, url: str) -> list[str]:
    """Find the redirect_uri values that a client_id advertises.

    We support two formats, checked in this order:

    IndieAuth 4.2.2

    The client SHOULD publish one or more <link> tags or Link HTTP headers with
    a rel attribute of redirect_uri at the client_id URL.

    OAuth Client ID Metadata Document
    (draft-ietf-oauth-client-id-metadata-document)

    The client_id URL returns a JSON document with a redirect_uris array. As we
    advertise client_id_metadata_document_supported in the authorization server
    metadata, we fall back to this format when no link tags are found.

    We read roughly the first 10kB of the page and a fetch error yields no
    redirect uris.

    We do not implement extracting redirect uris from headers.
    """
    body: bytes = b""
    status: int | None = None
    redirected = False
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp,
        ):
            status = resp.status
            redirected = bool(resp.history)
            async for data in resp.content.iter_chunked(1024):
                body += data

                if len(body) >= MAX_FETCH_BYTES:
                    break

    except TimeoutError:
        _LOGGER.error("Timeout while looking up redirect_uri %s", url)
        return []
    except aiohttp.client_exceptions.ClientSSLError:
        _LOGGER.error("SSL error while looking up redirect_uri %s", url)
        return []
    except aiohttp.client_exceptions.ClientOSError as ex:
        _LOGGER.error("OS error while looking up redirect_uri %s: %s", url, ex.strerror)
        return []
    except aiohttp.client_exceptions.ClientConnectionError:
        _LOGGER.error(
            "Low level connection error while looking up redirect_uri %s", url
        )
        return []
    except aiohttp.client_exceptions.ClientError:
        _LOGGER.error("Unknown error while looking up redirect_uri %s", url)
        return []

    if redirect_uris := _parse_link_tag_redirect_uris(url, body):
        return redirect_uris

    return _parse_metadata_document_redirect_uris(url, body, status, redirected)


def _parse_link_tag_redirect_uris(url: str, body: bytes) -> list[str]:
    """Find <link rel="redirect_uri"> values in the client_id page body."""
    parser = LinkTagParser("redirect_uri")
    parser.feed(body.decode(errors="replace"))

    # Authorization endpoints verifying that a redirect_uri is allowed for use
    # by a client MUST look for an exact match of the given redirect_uri in the
    # request against the list of redirect_uris discovered after resolving any
    # relative URLs.
    return [urljoin(url, found) for found in parser.found]


def _parse_metadata_document_redirect_uris(
    url: str, body: bytes, status: int | None, redirected: bool
) -> list[str]:
    """Parse the client_id page body as an OAuth Client ID Metadata Document.

    Per draft-ietf-oauth-client-id-metadata-document the document only counts
    when the client_id URL is https with a path and no fragment, the response
    was a direct 200 (not redirected), the document's client_id round-trips,
    and every redirect_uris entry is an absolute, fragment-free URI matched
    exactly. The url and its document are client-controlled and fetched
    unauthenticated, so rejections log at DEBUG (higher levels would be a
    log-flood vector).
    """
    # A body at the read cap may be truncated; a truncated prefix must not be
    # trusted even if it happens to be parseable.
    if (
        len(body) >= MAX_FETCH_BYTES
        or status != HTTPStatus.OK
        or redirected
        or not _is_valid_metadata_client_id(url)
    ):
        _LOGGER.debug(
            "Not treating %s as a client ID metadata document: body length %s,"
            " status %s, redirected %s (client_id must be a fragment-free https"
            " URL with a path)",
            url,
            len(body),
            status,
            redirected,
        )
        return []

    try:
        # Strict decode (RFC 8259 requires UTF-8): the link tag parser's
        # lenient replacement decode would mask invalid bytes as U+FFFD.
        document = json.loads(body.decode(), parse_constant=_reject_json_constant)
    except UnicodeDecodeError:
        _LOGGER.debug("Client ID metadata document at %s is not valid UTF-8", url)
        return []
    except ValueError:
        _LOGGER.debug("Client ID metadata document at %s is not valid JSON", url)
        return []

    if not isinstance(document, dict):
        _LOGGER.debug("Client ID metadata document at %s is not a JSON object", url)
        return []

    if document.get("client_id") != url:
        _LOGGER.debug(
            "Client ID metadata document at %s client_id does not match the"
            " document URL",
            url,
        )
        return []

    # redirect_uris entries are returned unmodified for RFC 6749 exact matching
    # rather than resolving relative references.
    redirect_uris = document.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not all(
        isinstance(redirect_uri, str) and _is_valid_metadata_redirect_uri(redirect_uri)
        for redirect_uri in redirect_uris
    ):
        _LOGGER.debug(
            "Client ID metadata document at %s has missing or invalid redirect_uris",
            url,
        )
        return []

    return redirect_uris


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
