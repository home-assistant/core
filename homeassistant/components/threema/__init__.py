"""The Threema Gateway integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import (
    ThreemaAPIClient,
    ThreemaAuthError,
    ThreemaConnectionError,
    ThreemaSendError,
)
from .const import CONF_API_SECRET, CONF_GATEWAY_ID, CONF_PRIVATE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [Platform.IMAGE]

type ThreemaConfigEntry = ConfigEntry[ThreemaAPIClient]

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_RECIPIENT = "recipient"
CONF_MESSAGE = "message"

RECIPIENT_SCHEMA = vol.All(
    cv.string,
    cv.matches_regex(r"^[0-9A-Za-z]{8}$"),
    lambda value: value.upper(),
)

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_RECIPIENT): RECIPIENT_SCHEMA,
        vol.Required(CONF_MESSAGE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Threema Gateway component."""

    async def async_send_message(call: ServiceCall) -> None:
        """Handle the send_message service call."""
        recipient = call.data[CONF_RECIPIENT]
        message = call.data[CONF_MESSAGE]

        # Get the config entry - auto-select if not specified
        entry_id = call.data.get(CONF_CONFIG_ENTRY_ID)

        if entry_id:
            entry = hass.config_entries.async_get_entry(entry_id)
            if not entry or entry.domain != DOMAIN:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_found",
                )
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                )
        else:
            # Auto-select: find any loaded Threema config entry
            entries = [
                e
                for e in hass.config_entries.async_entries(DOMAIN)
                if e.state is ConfigEntryState.LOADED
            ]
            if not entries:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="no_entries_found",
                )
            if len(entries) > 1:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="multiple_entries_found",
                )
            entry = entries[0]

        # Send the message
        client: ThreemaAPIClient = entry.runtime_data
        try:
            await client.send_text_message(recipient, message)
        except ThreemaAuthError as err:
            _LOGGER.warning(
                "Authentication failed sending message; check your Gateway credentials"
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except (ThreemaSendError, ThreemaConnectionError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_error",
                translation_placeholders={"error": str(err)},
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        async_send_message,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ThreemaConfigEntry) -> bool:
    """Set up Threema Gateway from a config entry."""
    client = ThreemaAPIClient(
        hass,
        gateway_id=entry.data[CONF_GATEWAY_ID],
        api_secret=entry.data[CONF_API_SECRET],
        private_key=entry.data.get(CONF_PRIVATE_KEY),
    )

    try:
        await client.validate_credentials()
    except ThreemaAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except ThreemaConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThreemaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
