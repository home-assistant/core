"""Helper functions for the Cert Expiry platform."""

import asyncio
import datetime
import socket
import ssl
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import get_default_context

from .const import TIMEOUT
from .errors import (
    ConnectionRefused,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)


async def async_get_cert(
    hass: HomeAssistant,
    host: str,
    port: int,
) -> dict[str, Any]:
    """Get the certificate for the host and port combination."""
    async with asyncio.timeout(TIMEOUT):
        transport, _ = await hass.loop.create_connection(
            asyncio.Protocol,
            host,
            port,
            ssl=get_default_context(),
            happy_eyeballs_delay=0.25,
            server_hostname=host,
        )
    try:
        return transport.get_extra_info("peercert")  # type: ignore[no-any-return]
    finally:
        transport.close()


async def get_cert_expiry_timestamp(
    hass: HomeAssistant,
    hostname: str,
    port: int,
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    try:
        cert = await async_get_cert(hass, hostname, port)
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

    ts_seconds = ssl.cert_time_to_seconds(cert["notAfter"])
    return dt_util.utc_from_timestamp(ts_seconds)
