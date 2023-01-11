"""The smtp component."""
from __future__ import annotations

import logging
import smtplib
import socket
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.ssl import client_context

from .const import CONF_DEBUG, CONF_ENCRYPTION, CONF_SERVER, DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the smtp component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up smtp from a config entry."""

    try:
        smtp_client = await hass.async_add_executor_job(
            get_smtp_client, dict(entry.data)
        )
        smtp_client.quit()

    except (socket.gaierror, ConnectionRefusedError) as err:
        _LOGGER.error(
            "SMTP server not found or refused connection (%s:%s). "
            "Please check the IP address, hostname, and availability of your SMTP server",
            entry.data[CONF_SERVER],
            entry.data[CONF_PORT],
        )
        raise ConfigEntryNotReady from err

    except smtplib.SMTPAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            "Login rejected. Please check your credentials"
        ) from err

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            dict(entry.data),
            hass.data[DATA_HASS_CONFIG],
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def get_smtp_client(entry: dict[str, Any]) -> smtplib.SMTP_SSL | smtplib.SMTP:
    """Connect/authenticate to SMTP Server."""
    ssl_context = client_context() if entry[CONF_VERIFY_SSL] else None
    if entry[CONF_ENCRYPTION] == "tls":
        mail: smtplib.SMTP_SSL | smtplib.SMTP = smtplib.SMTP_SSL(
            entry[CONF_SERVER],
            entry[CONF_PORT],
            context=ssl_context,
        )
    else:
        mail = smtplib.SMTP(entry[CONF_SERVER], entry[CONF_PORT])
    mail.set_debuglevel(entry[CONF_DEBUG])
    mail.ehlo_or_helo_if_needed()
    if entry[CONF_ENCRYPTION] == "starttls":
        mail.starttls(context=ssl_context)
    if CONF_USERNAME in entry and CONF_PASSWORD in entry:
        mail.login(entry[CONF_USERNAME], entry[CONF_PASSWORD])
    return mail
