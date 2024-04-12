"""The Netatmo integration."""

from __future__ import annotations

from http import HTTPStatus
import logging
import secrets
from typing import Any

import aiohttp
import pyatmo

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started
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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
        _LOGGER.warning("API error: %s (%s)", ex.status, ex.message)
        if ex.status in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex

    required_scopes = api.get_api_scopes(entry.data["auth_implementation"])
    if not (set(session.token["scope"]) & set(required_scopes)):
        _LOGGER.warning(
            "Session is missing scopes: %s",
            set(required_scopes) - set(session.token["scope"]),
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
        _: Any,
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
        _: Any,
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
            entry.async_on_unload(async_call_later(hass, 30, register_webhook))

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            await register_webhook(None)
        entry.async_on_unload(
            cloud.async_listen_connection_change(hass, manage_cloudhook)
        )
    else:
        entry.async_on_unload(async_at_started(hass, register_webhook))

    hass.services.async_register(DOMAIN, "register_webhook", register_webhook)
    hass.services.async_register(DOMAIN, "unregister_webhook", unregister_webhook)

    entry.async_on_unload(entry.add_update_listener(async_config_entry_updated))

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


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA_HANDLER]
    modules = [m for h in data.account.homes.values() for m in h.modules]
    rooms = [r for h in data.account.homes.values() for r in h.rooms]

    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1] in modules
        or identifier[1] in rooms
    )
