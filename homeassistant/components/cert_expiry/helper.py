"""Helper functions for the Cert Expiry platform."""

import asyncio
import datetime
import socket
import ssl

from cryptography.x509 import load_der_x509_certificate

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


async def async_get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
    *,
    verify_ssl: bool = True,
) -> bytes | None:
    """Get the certificate for the host and port combination."""
    async with asyncio.timeout(TIMEOUT):
        transport, _ = await hass.loop.create_connection(
            asyncio.Protocol,
            host,
            port,
            ssl=get_default_context()
            if verify_ssl
            else get_default_no_verify_context(),
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
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    try:
        cert = await async_get_cert(hass, hostname, port, verify_ssl=verify_ssl)
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
    except ValueError as err:
        raise ValidationFailure(
            f"Invalid certificate received from: {hostname}:{port}"
        ) from err
