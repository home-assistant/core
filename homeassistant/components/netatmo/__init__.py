"""The Netatmo integration."""

import logging
from typing import Any

from aiohttp import ClientError
import pyatmo

from homeassistant.components import cloud
from homeassistant.components.webhook import async_unregister as webhook_unregister
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import (
    DATA_CAMERAS,
    DATA_DEVICE_IDS,
    DATA_EVENTS,
    DATA_HOMES,
    DATA_PERSONS,
    DATA_SCHEDULES,
    DOMAIN,
    PLATFORMS,
)
from .data_handler import NetatmoConfigEntry, NetatmoDataHandler
from .services import async_setup_services
from .webhook import async_register_webhook, async_unregister_webhook

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

MAX_WEBHOOK_RETRIES = 3


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Netatmo component."""
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data[DOMAIN] = {
        DATA_PERSONS: {},
        DATA_DEVICE_IDS: {},
        DATA_SCHEDULES: {},
        DATA_HOMES: {},
        DATA_EVENTS: {},
        DATA_CAMERAS: {},
    }

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NetatmoConfigEntry) -> bool:
    """Set up Netatmo from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    # Set unique id if non was set (migration)
    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as ex:
        raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
    except (OAuth2TokenRequestError, ClientError) as ex:
        raise ConfigEntryNotReady from ex

    required_scopes = api.get_api_scopes(entry.data["auth_implementation"])
    if not (set(session.token["scope"]) & set(required_scopes)):
        _LOGGER.warning(
            "Session is missing scopes: %s",
            set(required_scopes) - set(session.token["scope"]),
        )
        raise ConfigEntryAuthFailed("Token scope not valid, trigger renewal")

    auth = api.AsyncConfigEntryNetatmoAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    data_handler = NetatmoDataHandler(hass, entry, auth)
    entry.runtime_data = data_handler
    await data_handler.async_setup()

    async def register_webhook(_: Any = None) -> None:
        await async_register_webhook(hass, entry)

    async def unregister_webhook(_: Any = None) -> None:
        await async_unregister_webhook(hass, entry)

    async def manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await register_webhook()

        if state is cloud.CloudConnectionState.CLOUD_DISCONNECTED:
            await unregister_webhook()
            entry.async_on_unload(async_call_later(hass, 30, register_webhook))

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            await register_webhook()
        entry.async_on_unload(
            cloud.async_listen_connection_change(hass, manage_cloudhook)
        )
    else:
        entry.async_on_unload(async_at_started(hass, register_webhook))

    entry.async_on_unload(entry.add_update_listener(async_config_entry_updated))

    return True


async def async_config_entry_updated(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}")


async def async_unload_entry(hass: HomeAssistant, entry: NetatmoConfigEntry) -> bool:
    """Unload a config entry."""
    if CONF_WEBHOOK_ID in entry.data:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        try:
            await entry.runtime_data.auth.async_dropwebhook()
        except pyatmo.ApiError:
            _LOGGER.debug("No webhook to be dropped")
        _LOGGER.debug("Unregister Netatmo webhook")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: NetatmoConfigEntry) -> None:
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
    hass: HomeAssistant, config_entry: NetatmoConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    data = config_entry.runtime_data
    modules = [m for h in data.account.homes.values() for m in h.modules]
    rooms = [r for h in data.account.homes.values() for r in h.rooms]

    return not any(
        identifier
        for identifier in device_entry.identifiers
        if (identifier[0] == DOMAIN and identifier[1] in modules)
        or identifier[1] in rooms
    )
