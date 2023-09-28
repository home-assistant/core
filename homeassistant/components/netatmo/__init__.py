"""The Netatmo integration."""
from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import logging
import secrets

import aiohttp
import pyatmo
from pyatmo.const import ALL_SCOPES as NETATMO_SCOPES
import voluptuous as vol

from homeassistant.components import cloud
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    Event,
    HomeAssistant,
    ServiceCall,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import (
    AUTH,
    CONF_CLOUDHOOK_URL,
    DATA_CAMERAS,
    DATA_DEVICE_IDS,
    DATA_EVENTS,
    DATA_HANDLER,
    DATA_HOMES,
    DATA_PERSONS,
    DATA_SCHEDULES,
    DOMAIN,
    PLATFORMS,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_PUSH_TYPE,
)
from .data_handler import NetatmoDataHandler
from .webhook import async_handle_webhook

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

MAX_WEBHOOK_RETRIES = 3


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Netatmo component."""
    hass.data[DOMAIN] = {
        DATA_PERSONS: {},
        DATA_DEVICE_IDS: {},
        DATA_SCHEDULES: {},
        DATA_HOMES: {},
        DATA_EVENTS: {},
        DATA_CAMERAS: {},
    }

    if DOMAIN not in config:
        return True

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
        ),
    )
    _LOGGER.warning(
        "Configuration of Netatmo integration in YAML is deprecated and "
        "will be removed in a future release; Your existing configuration "
        "(including OAuth Application Credentials) have been imported into "
        "the UI automatically and can be safely removed from your "
        "configuration.yaml file"
    )
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Netatmo",
        },
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netatmo from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    # Set unique id if non was set (migration)
    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        _LOGGER.debug("API error: %s (%s)", ex.status, ex.message)
        if ex.status in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex

    if entry.data["auth_implementation"] == cloud.DOMAIN:
        required_scopes = {
            scope
            for scope in NETATMO_SCOPES
            if scope not in ("access_doorbell", "read_doorbell")
        }
    else:
        required_scopes = set(NETATMO_SCOPES)

    if not (set(session.token["scope"]) & required_scopes):
        _LOGGER.debug(
            "Session is missing scopes: %s",
            required_scopes - set(session.token["scope"]),
        )
        raise ConfigEntryAuthFailed("Token scope not valid, trigger renewal")

    hass.data[DOMAIN][entry.entry_id] = {
        AUTH: api.AsyncConfigEntryNetatmoAuth(
            aiohttp_client.async_get_clientsession(hass), session
        )
    }

    data_handler = NetatmoDataHandler(hass, entry)
    hass.data[DOMAIN][entry.entry_id][DATA_HANDLER] = data_handler
    await data_handler.async_setup()

    async def unregister_webhook(
        call_or_event_or_dt: ServiceCall | Event | datetime | None,
    ) -> None:
        if CONF_WEBHOOK_ID not in entry.data:
            return
        _LOGGER.debug("Unregister Netatmo webhook (%s)", entry.data[CONF_WEBHOOK_ID])
        async_dispatcher_send(
            hass,
            f"signal-{DOMAIN}-webhook-None",
            {"type": "None", "data": {WEBHOOK_PUSH_TYPE: WEBHOOK_DEACTIVATION}},
        )
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        try:
            await hass.data[DOMAIN][entry.entry_id][AUTH].async_dropwebhook()
        except pyatmo.ApiError:
            _LOGGER.debug(
                "No webhook to be dropped for %s", entry.data[CONF_WEBHOOK_ID]
            )

    async def register_webhook(
        call_or_event_or_dt: ServiceCall | Event | datetime | None,
    ) -> None:
        if CONF_WEBHOOK_ID not in entry.data:
            data = {**entry.data, CONF_WEBHOOK_ID: secrets.token_hex()}
            hass.config_entries.async_update_entry(entry, data=data)

        if cloud.async_active_subscription(hass):
            webhook_url = await async_cloudhook_generate_url(hass, entry)
        else:
            webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])

        if entry.data[
            "auth_implementation"
        ] == cloud.DOMAIN and not webhook_url.startswith("https://"):
            _LOGGER.warning(
                "Webhook not registered - "
                "https and port 443 is required to register the webhook"
            )
            return

        webhook_register(
            hass,
            DOMAIN,
            "Netatmo",
            entry.data[CONF_WEBHOOK_ID],
            async_handle_webhook,
        )

        try:
            await hass.data[DOMAIN][entry.entry_id][AUTH].async_addwebhook(webhook_url)
            _LOGGER.info("Register Netatmo webhook: %s", webhook_url)
        except pyatmo.ApiError as err:
            _LOGGER.error("Error during webhook registration - %s", err)
        else:
            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
            )

    async def manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await register_webhook(None)

        if state is cloud.CloudConnectionState.CLOUD_DISCONNECTED:
            await unregister_webhook(None)
            async_call_later(hass, 30, register_webhook)

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            await register_webhook(None)
        cloud.async_listen_connection_change(hass, manage_cloudhook)

    elif hass.state == CoreState.running:
        await register_webhook(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register_webhook)

    hass.services.async_register(DOMAIN, "register_webhook", register_webhook)
    hass.services.async_register(DOMAIN, "unregister_webhook", unregister_webhook)

    entry.add_update_listener(async_config_entry_updated)

    return True


async def async_cloudhook_generate_url(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Generate the full URL for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        webhook_url = await cloud.async_create_cloudhook(
            hass, entry.data[CONF_WEBHOOK_ID]
        )
        data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
        hass.config_entries.async_update_entry(entry, data=data)
        return webhook_url
    return str(entry.data[CONF_CLOUDHOOK_URL])


async def async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN]

    if CONF_WEBHOOK_ID in entry.data:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        try:
            await data[entry.entry_id][AUTH].async_dropwebhook()
        except pyatmo.ApiError:
            _LOGGER.debug("No webhook to be dropped")
        _LOGGER.info("Unregister Netatmo webhook")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in data:
        data.pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup when entry is removed."""
    if CONF_WEBHOOK_ID in entry.data and cloud.async_active_subscription(hass):
        try:
            _LOGGER.debug(
                "Removing Netatmo cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass
