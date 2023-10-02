"""Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp.hdrs import METH_HEAD, METH_POST
from aiohttp.web import Request, Response
import voluptuous as vol
from withings_api.common import NotifyAppli

from homeassistant.components import cloud
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_generate_id as webhook_generate_id,
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .api import ConfigEntryWithingsApi
from .const import (
    CONF_CLOUDHOOK_URL,
    CONF_PROFILES,
    CONF_USE_WEBHOOK,
    DEFAULT_TITLE,
    DOMAIN,
    LOGGER,
)
from .coordinator import WithingsDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_PROFILES),
            cv.deprecated(CONF_CLIENT_ID),
            cv.deprecated(CONF_CLIENT_SECRET),
            vol.Schema(
                {
                    vol.Optional(CONF_CLIENT_ID): vol.All(cv.string, vol.Length(min=1)),
                    vol.Optional(CONF_CLIENT_SECRET): vol.All(
                        cv.string, vol.Length(min=1)
                    ),
                    vol.Optional(CONF_USE_WEBHOOK): cv.boolean,
                    vol.Optional(CONF_PROFILES): vol.All(
                        cv.ensure_list,
                        vol.Unique(),
                        vol.Length(min=1),
                        [vol.All(cv.string, vol.Length(min=1))],
                    ),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Withings component."""

    if conf := config.get(DOMAIN):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Withings",
            },
        )
        if CONF_CLIENT_ID in conf:
            await async_import_client_credential(
                hass,
                DOMAIN,
                ClientCredential(
                    conf[CONF_CLIENT_ID],
                    conf[CONF_CLIENT_SECRET],
                ),
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Withings from a config entry."""
    if CONF_WEBHOOK_ID not in entry.data or entry.unique_id is None:
        new_data = entry.data.copy()
        unique_id = str(entry.data[CONF_TOKEN]["userid"])
        if CONF_WEBHOOK_ID not in new_data:
            new_data[CONF_WEBHOOK_ID] = webhook_generate_id()

        hass.config_entries.async_update_entry(
            entry, data=new_data, unique_id=unique_id
        )

    client = ConfigEntryWithingsApi(
        hass=hass,
        config_entry=entry,
        implementation=await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        ),
    )
    coordinator = WithingsDataUpdateCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def unregister_webhook(
        _: Any,
    ) -> None:
        LOGGER.debug("Unregister Withings webhook (%s)", entry.data[CONF_WEBHOOK_ID])
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        await hass.data[DOMAIN][entry.entry_id].async_unsubscribe_webhooks()

    async def register_webhook(
        _: Any,
    ) -> None:
        if cloud.async_active_subscription(hass):
            webhook_url = await async_cloudhook_generate_url(hass, entry)
        else:
            webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])

        if not webhook_url.startswith("https://"):
            LOGGER.warning(
                "Webhook not registered - "
                "https and port 443 is required to register the webhook"
            )
            return

        webhook_name = "Withings"
        if entry.title != DEFAULT_TITLE:
            webhook_name = " ".join([DEFAULT_TITLE, entry.title])

        webhook_register(
            hass,
            DOMAIN,
            webhook_name,
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(coordinator),
        )

        await hass.data[DOMAIN][entry.entry_id].async_subscribe_webhooks(webhook_url)
        LOGGER.debug("Register Withings webhook: %s", webhook_url)
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
    else:
        async_at_started(hass, register_webhook)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


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


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup when entry is removed."""
    if cloud.async_active_subscription(hass):
        try:
            LOGGER.debug(
                "Removing Withings cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass


def json_message_response(message: str, message_code: int) -> Response:
    """Produce common json output."""
    return HomeAssistantView.json({"message": message, "code": message_code})


def get_webhook_handler(
    coordinator: WithingsDataUpdateCoordinator,
) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
    """Return webhook handler."""

    async def async_webhook_handler(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        # Handle http head calls to the path.
        # When creating a notify subscription, Withings will check that the endpoint is running by sending a HEAD request.
        if request.method == METH_HEAD:
            return Response()

        if request.method != METH_POST:
            return json_message_response("Invalid method", message_code=2)

        # Handle http post calls to the path.
        if not request.body_exists:
            return json_message_response("No request body", message_code=12)

        params = await request.post()

        if "appli" not in params:
            return json_message_response(
                "Parameter appli not provided", message_code=20
            )

        try:
            appli = NotifyAppli(int(params.getone("appli")))  # type: ignore[arg-type]
        except ValueError:
            return json_message_response("Invalid appli provided", message_code=21)

        await coordinator.async_webhook_data_updated(appli)

        return json_message_response("Success", message_code=0)

    return async_webhook_handler
