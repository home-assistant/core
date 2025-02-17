"""Helper functions for the Cert Expiry platform."""

import datetime
import logging
import socket
import ssl
import zoneinfo

import OpenSSL.crypto

from homeassistant.util.ssl import get_default_context

from .const import TIMEOUT
from .errors import (
    ConnectionRefused,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)

_LOGGER = logging.getLogger(__name__)


def async_get_cert(
    host: str,
    port: int,
) -> OpenSSL.crypto.X509 | None:
    """Get the certificate for the host and port combination."""

    context = get_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.verify_flags = context.verify_flags | ssl.VERIFY_CRL_CHECK_CHAIN

    conn = socket.create_connection((host, port), timeout=TIMEOUT)
    sock = context.wrap_socket(conn, server_hostname=host)
    try:
        der_cert = sock.getpeercert(True)
    finally:
        sock.close()
    if der_cert is None:
        return None
    return OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, der_cert)


def get_cert_expiry_timestamp(
    hostname: str,
    port: int,
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    try:
        cert = async_get_cert(hostname, port)
    except socket.gaierror as err:
        raise ResolveFailed(f"Cannot resolve hostname: {hostname}") from err
    except TimeoutError as err:
        raise ConnectionTimeout(
            f"Connection timeout with server: {hostname}:{port}"
        ) from err
    except ConnectionRefusedError as err:
        raise ConnectionRefused(
            f"Connection refused by server: {hostname}:{port}"
        ) from err
    except ssl.CertificateError as err:
        raise ValidationFailure(err.verify_message) from err
    except ssl.SSLError as err:
        raise ValidationFailure(err.args[0]) from err

    if cert is None:
        raise ValidationFailure(
            f"No certificate received from server: {hostname}:{port}"
        )

    not_after = cert.get_notAfter()
    if not_after is None:
        raise ValidationFailure(
            f"No expiry date in certificate from server: {hostname}:{port}"
        )
    return datetime.datetime.strptime(
        not_after.decode(encoding="ascii"), "%Y%m%d%H%M%SZ"
    ).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
