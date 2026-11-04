"""CA certificates trusted by Home Assistant HTTP clients."""

from functools import cache
import ssl

import certifi


@cache
def certifi_ca_data() -> bytes:
    """Return the certifi CA certificates in DER form.

    Cached, so later SSL contexts can load them with cadata, which does not
    read from disk. The certifi bundle only contains CA certificates, so
    exporting them with get_ca_certs() loses nothing.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=certifi.where())
    return b"".join(context.get_ca_certs(binary_form=True))
