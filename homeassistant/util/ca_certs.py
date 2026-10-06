"""CA certificates trusted by Home Assistant HTTP clients."""

from functools import cache
import ssl

import certifi


@cache
def load_ca_data(cafile: str) -> bytes:
    """Return the CA certificates in cafile in DER form.

    Cached, so later SSL contexts can load them with cadata, which does not
    read from disk.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=cafile)
    return b"".join(context.get_ca_certs(binary_form=True))


def certifi_ca_data() -> bytes:
    """Return the certifi CA certificates in DER form."""
    return load_ca_data(certifi.where())
