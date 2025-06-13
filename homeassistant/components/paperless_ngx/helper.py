"""Helper functions for Paperless NGX integration."""

import ssl

from homeassistant.core import HomeAssistant


async def get_ssl_context(hass: HomeAssistant, verify_ssl: bool) -> ssl.SSLContext:
    """Create an SSL context for Paperless NGX API requests."""

    context = await hass.async_add_executor_job(ssl.create_default_context)

    if not verify_ssl:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    return context
