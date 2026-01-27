"""The smtp component."""

from __future__ import annotations

import contextlib
import smtplib
import socket
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import template
from homeassistant.helpers.selector import (
    ConfigEntrySelector,
    ConfigEntrySelectorConfig,
)
from homeassistant.util.ssl import client_context

from .const import (
    ATTR_FROM_NAME,
    ATTR_HTML,
    ATTR_IMAGES,
    ATTR_MESSAGE,
    ATTR_SUBJECT,
    ATTR_TO,
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)

PLATFORMS = [Platform.SENSOR]

CONF_CONFIG_ENTRY = "config_entry"

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector(
            ConfigEntrySelectorConfig(integration=DOMAIN)
        ),
        vol.Optional(ATTR_MESSAGE, default=""): cv.string,
        vol.Optional(ATTR_SUBJECT): cv.string,
        vol.Optional(ATTR_TO): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_FROM_NAME): cv.string,
        vol.Optional(ATTR_HTML): cv.string,
        vol.Optional(ATTR_IMAGES): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMTP from a config entry."""
    # Validate connection
    error = await hass.async_add_executor_job(
        _try_connect,
        entry.data[CONF_SERVER],
        entry.data[CONF_PORT],
        entry.data[CONF_TIMEOUT],
        entry.data[CONF_ENCRYPTION],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        entry.data[CONF_VERIFY_SSL],
    )

    if error == "invalid_auth":
        raise ConfigEntryAuthFailed("Invalid SMTP credentials")
    if error:
        raise ConfigEntryNotReady(f"Unable to connect to SMTP server: {error}")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "config": entry.data,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the send_message service (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):

        async def async_send_message(call: ServiceCall) -> None:
            """Handle the send_message service call."""
            # Import here to avoid circular imports
            from .notify import MailNotificationService

            # Get the config entry
            entry_id = call.data[CONF_CONFIG_ENTRY]
            if entry_id not in hass.data[DOMAIN]:
                raise ValueError(f"Config entry {entry_id} not found")

            entry_data = hass.data[DOMAIN][entry_id]
            data = entry_data["config"]
            verify_ssl = data[CONF_VERIFY_SSL]
            ssl_context = client_context() if verify_ssl else None

            service = MailNotificationService(
                server=data[CONF_SERVER],
                port=data[CONF_PORT],
                timeout=data[CONF_TIMEOUT],
                sender=data[CONF_SENDER],
                encryption=data[CONF_ENCRYPTION],
                username=data.get(CONF_USERNAME),
                password=data.get(CONF_PASSWORD),
                recipients=data[CONF_RECIPIENT],
                sender_name=data.get(CONF_SENDER_NAME),
                debug=data[CONF_DEBUG],
                verify_ssl=verify_ssl,
                ssl_context=ssl_context,
            )
            service.hass = hass

            # Render templates
            def render_template(value: str) -> str:
                """Render a template string."""
                if not value:
                    return value
                tpl = template.Template(value, hass)
                return str(tpl.async_render(parse_result=False))

            # Render message with templates
            message_text = render_template(call.data.get(ATTR_MESSAGE, ""))

            # Build kwargs for send_message
            kwargs: dict[str, Any] = {}

            if ATTR_SUBJECT in call.data:
                kwargs["title"] = render_template(call.data[ATTR_SUBJECT])

            if ATTR_TO in call.data and call.data[ATTR_TO]:
                kwargs["target"] = call.data[ATTR_TO]

            # Build data dict for html, images, from_name
            msg_data: dict[str, Any] = {}
            if ATTR_HTML in call.data:
                msg_data[ATTR_HTML] = render_template(call.data[ATTR_HTML])
            if ATTR_IMAGES in call.data:
                msg_data[ATTR_IMAGES] = call.data[ATTR_IMAGES]
            if ATTR_FROM_NAME in call.data:
                msg_data[ATTR_FROM_NAME] = render_template(call.data[ATTR_FROM_NAME])

            if msg_data:
                kwargs["data"] = msg_data

            sensors = entry_data.get("sensors", {})

            def _send() -> None:
                service.send_message(message_text, **kwargs)

            try:
                await hass.async_add_executor_job(_send)
                # Update sensors on success
                if sensors.get("last_error"):
                    sensors["last_error"].update_error(None)
                if sensors.get("last_sent"):
                    sensors["last_sent"].update_sent()
            except Exception as err:
                # Update sensors on error
                if sensors.get("last_error"):
                    sensors["last_error"].update_error(str(err))
                raise

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            async_send_message,
            schema=SERVICE_SEND_MESSAGE_SCHEMA,
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    hass.data[DOMAIN][entry.entry_id]["config"] = entry.data


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Only remove service if no more entries
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)

    return unload_ok


def _try_connect(
    server: str,
    port: int,
    timeout: int,
    encryption: str,
    username: str | None,
    password: str | None,
    verify_ssl: bool,
) -> str | None:
    """Try to connect to the SMTP server and return error key if failed."""
    ssl_context = client_context() if verify_ssl else None
    mail: smtplib.SMTP_SSL | smtplib.SMTP | None = None

    try:
        if encryption == "tls":
            mail = smtplib.SMTP_SSL(
                server,
                port,
                timeout=timeout,
                context=ssl_context,
            )
        else:
            mail = smtplib.SMTP(server, port, timeout=timeout)

        mail.ehlo_or_helo_if_needed()

        if encryption == "starttls":
            mail.starttls(context=ssl_context)
            mail.ehlo()

        if username and password:
            mail.login(username, password)

        return None

    except smtplib.SMTPAuthenticationError:
        return "invalid_auth"
    except smtplib.SMTPException:
        return "cannot_connect"
    except (socket.gaierror, ConnectionRefusedError, TimeoutError, OSError):
        return "cannot_connect"
    finally:
        if mail:
            with contextlib.suppress(smtplib.SMTPException):
                mail.quit()
