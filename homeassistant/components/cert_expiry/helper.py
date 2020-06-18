"""Helper functions for the Cert Expiry platform."""
import socket
import ssl

from homeassistant.util import dt

from .const import TIMEOUT
from .errors import (
    ConnectionRefused,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)


def get_cert(host, port):
    """Get the certificate for the host and port combination."""
    ctx = ssl.create_default_context()
    address = (host, port)
    with socket.create_connection(address, timeout=TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=address[0]) as ssock:
            # pylint disable: https://github.com/PyCQA/pylint/issues/3166
            cert = ssock.getpeercert()  # pylint: disable=no-member
            return cert


async def get_cert_expiry_timestamp(hass, hostname, port):
    """Return the certificate's expiration timestamp."""
    try:
        cert = await hass.async_add_executor_job(get_cert, hostname, port)
    except socket.gaierror:
        raise ResolveFailed(f"Cannot resolve hostname: {hostname}")
    except socket.timeout:
        raise ConnectionTimeout(f"Connection timeout with server: {hostname}:{port}")
    except ConnectionRefusedError:
        raise ConnectionRefused(f"Connection refused by server: {hostname}:{port}")
    except ssl.CertificateError as err:
        raise ValidationFailure(err.verify_message)
    except ssl.SSLError as err:
        raise ValidationFailure(err.args[0])

    ts_seconds = ssl.cert_time_to_seconds(cert["notAfter"])
    return dt.utc_from_timestamp(ts_seconds)
