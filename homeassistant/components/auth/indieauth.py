"""Helpers to resolve client ID/secret."""
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse

# IP addresses of loopback interfaces
ALLOWED_IPS = (
    ip_address('127.0.0.1'),
    ip_address('::1'),
)

# RFC1918 - Address allocation for Private Internets
ALLOWED_NETWORKS = (
    ip_network('10.0.0.0/8'),
    ip_network('172.16.0.0/12'),
    ip_network('192.168.0.0/16'),
)


def verify_redirect_uri(client_id, redirect_uri):
    """Verify that the client and redirect uri match."""
    try:
        client_id_parts = _parse_client_id(client_id)
    except ValueError:
        return False

    redirect_parts = _parse_url(redirect_uri)

    # IndieAuth 4.2.2 allows for redirect_uri to be on different domain
    # but needs to be specified in link tag when fetching `client_id`.
    # This is not implemented.

    # Verify redirect url and client url have same scheme and domain.
    return (
        client_id_parts.scheme == redirect_parts.scheme and
        client_id_parts.netloc == redirect_parts.netloc
    )


def verify_client_id(client_id):
    """Verify that the client id is valid."""
    try:
        _parse_client_id(client_id)
        return True
    except ValueError:
        return False


def _parse_url(url):
    """Parse a url in parts and canonicalize according to IndieAuth."""
    parts = urlparse(url)

    # Canonicalize a url according to IndieAuth 3.2.

    # SHOULD convert the hostname to lowercase
    parts = parts._replace(netloc=parts.netloc.lower())

    # If a URL with no path component is ever encountered,
    # it MUST be treated as if it had the path /.
    if parts.path == '':
        parts = parts._replace(path='/')

    return parts


def _parse_client_id(client_id):
    """Test if client id is a valid URL according to IndieAuth section 3.2.

    https://indieauth.spec.indieweb.org/#client-identifier
    """
    parts = _parse_url(client_id)

    # Client identifier URLs
    # MUST have either an https or http scheme
    if parts.scheme not in ('http', 'https'):
        raise ValueError()

    # MUST contain a path component
    # Handled by url canonicalization.

    # MUST NOT contain single-dot or double-dot path segments
    if any(segment in ('.', '..') for segment in parts.path.split('/')):
        raise ValueError(
            'Client ID cannot contain single-dot or double-dot path segments')

    # MUST NOT contain a fragment component
    if parts.fragment != '':
        raise ValueError('Client ID cannot contain a fragment')

    # MUST NOT contain a username or password component
    if parts.username is not None:
        raise ValueError('Client ID cannot contain username')

    if parts.password is not None:
        raise ValueError('Client ID cannot contain password')

    # MAY contain a port
    try:
        # parts raises ValueError when port cannot be parsed as int
        parts.port
    except ValueError:
        raise ValueError('Client ID contains invalid port')

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
        if netloc[0] == '[' and netloc[-1] == ']':
            netloc = netloc[1:-1]

        address = ip_address(netloc)
    except ValueError:
        # Not an ip address
        pass

    if (address is None or
            address in ALLOWED_IPS or
            any(address in network for network in ALLOWED_NETWORKS)):
        return parts

    raise ValueError('Hostname should be a domain name or local IP address')
