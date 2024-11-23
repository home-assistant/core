"""Helper functions for the Cert Expiry platform."""

import asyncio
import datetime
import socket
import ssl

from cryptography.x509 import Certificate, load_der_x509_certificate

from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import get_default_no_verify_context

from .const import TIMEOUT
from .errors import (
    CertificateExpiredFailure,
    ConnectionRefused,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)


async def async_get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
) -> Certificate:
    """Get the certificate for the host and port combination."""
    async with asyncio.timeout(TIMEOUT):
        transport, _ = await hass.loop.create_connection(
            asyncio.Protocol,
            host,
            port,
            ssl=get_default_no_verify_context(),
            happy_eyeballs_delay=0.25,
            server_hostname=host,
        )
    try:
        der_certificate = transport.get_extra_info("ssl_object").getpeercert(True)
        return load_der_x509_certificate(der_certificate)
    finally:
        transport.close()


async def get_cert_expiry_timestamp(
    hass: HomeAssistant,
    hostname: str,
    port: int,
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    try:
        cert: Certificate = await async_get_cert(hass, hostname, port)
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
    except ssl.SSLError as err:
        raise ValidationFailure(err.args[0]) from err

    return cert.not_valid_after_utc


async def validate_cert_expiry(
    timestamp: datetime.datetime,
) -> bool:
    """Validate that timestamp has not expired."""
    if datetime.datetime.now(datetime.UTC) > timestamp:
        raise CertificateExpiredFailure("Certificate has expired")

    return True
