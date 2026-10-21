"""Helper functions for the Cert Expiry platform."""

import asyncio
import datetime as dt
import socket
import ssl

from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import (
    InvalidVersion,
    load_der_x509_certificate,
    load_pem_x509_certificates,
)

from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import (
    SSL_ALPN_HTTP11,
    create_client_context,
    get_default_context,
    get_default_no_verify_context,
)

from .const import TIMEOUT
from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    InvalidCACertificate,
    ResolveFailed,
    ValidationFailure,
)


def normalize_ca_certificates(ca_certificates: str) -> str:
    """Validate and normalize a PEM bundle containing only certificates."""
    if not ca_certificates.strip():
        return ""
    try:
        certificates = load_pem_x509_certificates(ca_certificates.encode("ascii"))
    except (ValueError, InvalidVersion) as err:
        raise InvalidCACertificate("Invalid PEM certificates") from err

    normalized = "".join(
        certificate.public_bytes(Encoding.PEM).decode("ascii")
        for certificate in certificates
    )
    if "".join(ca_certificates.split()) != "".join(normalized.split()):
        raise InvalidCACertificate("The PEM bundle must contain only certificates")
    return normalized


def _create_ssl_context(ca_certificates: str, verify_ssl: bool) -> ssl.SSLContext:
    """Create a context with additional trust without modifying shared contexts."""
    ca_certificates = normalize_ca_certificates(ca_certificates)
    if not verify_ssl:
        return get_default_no_verify_context()

    context = create_client_context(alpn_protocols=SSL_ALPN_HTTP11)
    try:
        context.load_verify_locations(cadata=ca_certificates)
    except ssl.SSLError as err:
        raise InvalidCACertificate("Unable to load PEM certificates") from err
    return context


async def async_get_ssl_context(
    hass: HomeAssistant,
    *,
    verify_ssl: bool = True,
    ca_certificates: str = "",
) -> ssl.SSLContext:
    """Prepare the TLS context once for a config flow or config entry."""
    if ca_certificates:
        return await hass.async_add_executor_job(
            _create_ssl_context, ca_certificates, verify_ssl
        )
    if verify_ssl:
        return get_default_context()
    return get_default_no_verify_context()


async def async_get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
    *,
    verify_ssl: bool = True,
    ssl_context: ssl.SSLContext | None = None,
) -> bytes | None:
    """Get the certificate for the host and port combination."""
    if ssl_context is None:
        ssl_context = (
            get_default_context() if verify_ssl else get_default_no_verify_context()
        )
    async with asyncio.timeout(TIMEOUT):
        transport, _ = await hass.loop.create_connection(
            asyncio.Protocol,
            host,
            port,
            ssl=ssl_context,
            happy_eyeballs_delay=0.25,
            server_hostname=host,
        )
    try:
        ssl_object: ssl.SSLObject = transport.get_extra_info("ssl_object")
        return ssl_object.getpeercert(binary_form=True)
    finally:
        transport.close()


async def get_cert_expiry_timestamp(
    hass: HomeAssistant,
    hostname: str,
    port: int,
    *,
    verify_ssl: bool = True,
    ssl_context: ssl.SSLContext | None = None,
) -> dt.datetime:
    """Return the certificate's expiration timestamp."""
    try:
        cert = await async_get_cert(
            hass, hostname, port, verify_ssl=verify_ssl, ssl_context=ssl_context
        )
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

    if not cert:
        raise ValidationFailure(
            f"No certificate expiration found for: {hostname}:{port}"
        )

    try:
        return load_der_x509_certificate(cert).not_valid_after_utc
    except (ValueError, InvalidVersion) as err:
        raise ValidationFailure(
            f"Invalid certificate received from: {hostname}:{port}"
        ) from err
