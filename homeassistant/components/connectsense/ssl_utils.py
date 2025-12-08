from __future__ import annotations

import ssl
import ipaddress
import logging
from pathlib import Path
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

# Embedded CA (your PEM file lives here)
_EMBEDDED_CA = Path(__file__).parent / "certs" / "device_ca.pem"


def _build_ctx_from_embedded_ca() -> ssl.SSLContext:
    """
    Build an SSLContext WITHOUT loading system defaults (avoids blocking calls),
    and trust only the embedded CA. Hostname checking remains enabled.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    # Only load our CA; do NOT call load_default_certs()
    ctx.load_verify_locations(cafile=str(_EMBEDDED_CA))
    return ctx


async def get_aiohttp_ssl(hass, entry):
    """
    Returns the object you should pass to aiohttp's 'ssl=' parameter:
      - False  -> disable verification (when host is an IP to avoid hostname mismatch)
      - SSLContext -> use embedded CA (when host is a hostname and CA is present)
      - None   -> use aiohttp default (system trust store) if no embedded CA
    """
    host = (entry.data.get(CONF_HOST) or "").strip()

    # If the configured host is an IP, skip certificate verification (still TLS-encrypted).
    try:
        if host:
            ipaddress.ip_address(host)
            return False
    except ValueError:
        # Not an IP => treat as hostname; verify if we can.
        pass

    if _EMBEDDED_CA.exists():
        # Build the context in a worker thread to avoid blocking the loop
        return await hass.async_add_executor_job(_build_ctx_from_embedded_ca)

    # No embedded CA: let aiohttp use its default context (may fail with self-signed certs)
    _LOGGER.debug("ssl_utils: embedded CA not found at %s; using default SSL context", _EMBEDDED_CA)
    return None
