"""Helper functions for the Cert Expiry platform."""

import datetime
import logging
import socket
import ssl

import certifi.core
import cryptography.x509
from cryptography.x509 import Certificate
from OpenSSL.crypto import (
    FILETYPE_ASN1,
    X509,
    X509Store,
    X509StoreContext,
    X509StoreContextError,
    load_certificate,
)

from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import TIMEOUT
from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)

_LOGGER = logging.getLogger(__name__)


def verify_cert(cert: Certificate):
    """Verifies the certificate against the system store."""
    ssl_context = get_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.verify_flags = ssl_context.verify_flags | ssl.VERIFY_CRL_CHECK_CHAIN

    trusted_store = X509Store()

    system_certs_count = 0
    for sys_cert_der in ssl_context.get_ca_certs(binary_form=True):
        try:
            # Load the system cert into pyOpenSSL format
            ca_cert = load_certificate(FILETYPE_ASN1, sys_cert_der)
            trusted_store.add_cert(ca_cert)
            system_certs_count += 1
        except Exception:  # noqa: BLE001
            # Skip invalid system certificate
            continue

    # fallback: If certificates can't be found using SSLContext, use certifi
    if system_certs_count == 0:
        _LOGGER.warning("System store returned 0 certs. Falling back to certifi.")
        trusted_store.load_locations(certifi.where())

    cert = X509.from_cryptography(cert)

    verify_context = X509StoreContext(trusted_store, cert)
    try:
        verify_context.verify_certificate()
    except X509StoreContextError as err:
        raise ValidationFailure(err.args[0]) from err


def _get_cert_sync(
    hostname: str,
    port: int,
) -> Certificate:
    """Get the certificate for the host and port combination."""

    context = get_default_no_verify_context()

    try:
        conn = socket.create_connection((hostname, port), timeout=TIMEOUT)
        sock = context.wrap_socket(conn, server_hostname=hostname)
        try:
            der_cert = sock.getpeercert(True)
        finally:
            sock.close()
        if der_cert is None:
            cert = None
        else:
            cert = cryptography.x509.load_der_x509_certificate(der_cert)
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
    except ConnectionResetError as err:
        raise ConnectionReset(f"Connection reset by server: {hostname}:{port}") from err
    except ssl.CertificateError as err:
        raise ValidationFailure(err.verify_message) from err
    except ssl.SSLError as err:
        raise ValidationFailure(err.args[0]) from err

    if cert is None:
        raise ValidationFailure(
            f"No certificate received from server: {hostname}:{port}"
        )

    return cert


async def get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
) -> Certificate:
    """Get the certificate for the host and port combination."""

    return await hass.async_add_executor_job(
        _get_cert_sync,
        host,
        port,
    )


def get_cert_expiry_timestamp(
    cert: Certificate | None,
    hostname: str,
    port: int,
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    not_after = cert.not_valid_after_utc
    if not_after is None:
        raise ValidationFailure(
            f"No expiry date in certificate from server: {hostname}:{port}"
        )
    return not_after
