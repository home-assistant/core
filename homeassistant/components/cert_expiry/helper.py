"""Helper functions for the Cert Expiry platform."""
from functools import cache
import socket
import ssl

from cryptography import x509

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import TIMEOUT
from .errors import (
    ConnectionRefused,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)


@cache
def _get_ssl_context() -> ssl.SSLContext:
    """Return the SSL context."""
    ctx = ssl.SSLContext()
    return ctx


def get_cert(host: str, port: int):
    """Get the certificate for the host and port combination."""
    ctx = _get_ssl_context()
    address = (host, port)
    with socket.create_connection(
        address,
        timeout=TIMEOUT,
    ) as sock, ctx.wrap_socket(sock, server_hostname=address[0]) as ssock:
        # Request certificate in binary form as otherwise invalid cert will not be retrieved
        binary_cert = ssock.getpeercert(True)
        if binary_cert is None:
            raise ValidationFailure("Unable to retrieve peer certificate")

        decoded_cert = x509.load_der_x509_certificate(binary_cert)
        return decoded_cert


async def get_cert_expiry_timestamp(
    hass: HomeAssistant,
    hostname: str,
    port: int,
):
    """Return the certificate's expiration timestamp."""
    try:
        cert = await hass.async_add_executor_job(get_cert, hostname, port)
    except socket.gaierror as err:
        raise ResolveFailed(f"Cannot resolve hostname: {hostname}") from err
    except socket.timeout as err:
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

    return dt_util.as_utc(cert.not_valid_after)
