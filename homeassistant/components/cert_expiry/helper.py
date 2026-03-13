"""Helper functions for the Cert Expiry platform."""

import asyncio
import datetime
import functools
import socket
import ssl
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import get_default_context

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
    ignore_hostname: bool,
    ca_data: str | None,
) -> dict[str, Any]:
    """Get the certificate for the host and port combination."""
    async with asyncio.timeout(TIMEOUT):
        if ca_data:
            context = await hass.async_add_executor_job(
                functools.partial(
                    ssl.create_default_context,
                    ssl.Purpose.SERVER_AUTH,
                    cadata=ca_data,
                    cafile=None,
                    capath=None,
                )
            )
        else:
            context = get_default_context()
        context.check_hostname = not ignore_hostname
        transport, _ = await hass.loop.create_connection(
            asyncio.Protocol,
            host,
            port,
            ssl=context,
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
    ignore_hostname: bool,
    ca_data: str | None,
) -> datetime.datetime:
    """Return the certificate's expiration timestamp."""
    try:
        cert = await async_get_cert(hass, hostname, port, ignore_hostname, ca_data)
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

    ts_seconds = ssl.cert_time_to_seconds(cert["notAfter"])
    return dt_util.utc_from_timestamp(ts_seconds)
