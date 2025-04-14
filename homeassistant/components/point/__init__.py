"""Support for Minut Point."""

from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientResponseError, web
from pypoint import PointSession

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import api
from .const import CONF_WEBHOOK_URL, DOMAIN, EVENT_RECEIVED, SIGNAL_WEBHOOK
from .coordinator import PointDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type PointConfigEntry = ConfigEntry[PointDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PointConfigEntry) -> bool:
    """Set up Minut Point from a config entry."""

    if "auth_implementation" not in entry.data:
        raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.")

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if err.status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    point_session = PointSession(auth)

    coordinator = PointDataUpdateCoordinator(hass, point_session)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await async_setup_webhook(hass, entry, point_session)
    await hass.config_entries.async_forward_entry_setups(
        entry, [*PLATFORMS, Platform.ALARM_CONTROL_PANEL]
    )

    return True


async def async_setup_webhook(
    hass: HomeAssistant, entry: PointConfigEntry, session: PointSession
) -> None:
    """Set up a webhook to handle binary sensor events."""
    if CONF_WEBHOOK_ID not in entry.data:
        webhook_id = webhook.async_generate_id()
        webhook_url = webhook.async_generate_url(hass, webhook_id)
        _LOGGER.debug("Registering new webhook at: %s", webhook_url)

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_WEBHOOK_ID: webhook_id,
                CONF_WEBHOOK_URL: webhook_url,
            },
        )

    await session.update_webhook(
        webhook.async_generate_url(hass, entry.data[CONF_WEBHOOK_ID]),
        entry.data[CONF_WEBHOOK_ID],
        ["*"],
    )
    webhook.async_register(
        hass, DOMAIN, "Point", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )


async def async_unload_entry(hass: HomeAssistant, entry: PointConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, [*PLATFORMS, Platform.ALARM_CONTROL_PANEL]
    ):
        session = entry.runtime_data.point
        if CONF_WEBHOOK_ID in entry.data:
            webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
            await session.remove_webhook()
    return unload_ok


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> None:
    """Handle webhook callback."""
    try:
        data = await request.json()
        _LOGGER.debug("Webhook %s: %s", webhook_id, data)
    except ValueError:
        return

    if isinstance(data, dict):
        data["webhook_id"] = webhook_id
        async_dispatcher_send(hass, SIGNAL_WEBHOOK, data, data.get("hook_id"))
    hass.bus.async_fire(EVENT_RECEIVED, data)
