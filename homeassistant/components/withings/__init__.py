"""Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiohttp.web import Request, Response
import voluptuous as vol
from withings_api.common import NotifyAppli

from homeassistant.components import webhook
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_generate_id,
    async_unregister as async_unregister_webhook,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from . import const
from .api import ConfigEntryWithingsApi
from .const import CONF_USE_WEBHOOK, CONFIG, LOGGER
from .coordinator import (
    BaseWithingsDataUpdateCoordinator,
    PollingWithingsDataUpdateCoordinator,
    WebhookWithingsDataUpdateCoordinator,
)

DOMAIN = const.DOMAIN
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(const.CONF_PROFILES),
            cv.deprecated(CONF_CLIENT_ID),
            cv.deprecated(CONF_CLIENT_SECRET),
            vol.Schema(
                {
                    vol.Optional(CONF_CLIENT_ID): vol.All(cv.string, vol.Length(min=1)),
                    vol.Optional(CONF_CLIENT_SECRET): vol.All(
                        cv.string, vol.Length(min=1)
                    ),
                    vol.Optional(const.CONF_USE_WEBHOOK): cv.boolean,
                    vol.Optional(const.CONF_PROFILES): vol.All(
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
    if not (conf := config.get(DOMAIN)):
        # Apply the defaults.
        conf = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
        hass.data[DOMAIN] = {const.CONFIG: conf}
        return True

    hass.data[DOMAIN] = {const.CONFIG: conf}

    # Setup the oauth2 config flow.
    if CONF_CLIENT_ID in conf:
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(
                conf[CONF_CLIENT_ID],
                conf[CONF_CLIENT_SECRET],
            ),
        )
        LOGGER.warning(
            "Configuration of Withings integration OAuth2 credentials in YAML "
            "is deprecated and will be removed in a future release; Your "
            "existing OAuth Application Credentials have been imported into "
            "the UI automatically and can be safely removed from your "
            "configuration.yaml file"
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Withings from a config entry."""
    if CONF_USE_WEBHOOK not in entry.options:
        new_data = entry.data.copy()
        new_options = {
            CONF_USE_WEBHOOK: new_data.get(CONF_USE_WEBHOOK, False),
        }
        unique_id = str(entry.data[CONF_TOKEN]["userid"])
        if CONF_WEBHOOK_ID not in new_data:
            new_data[CONF_WEBHOOK_ID] = async_generate_id()

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, unique_id=unique_id
        )
    use_webhook = hass.data[DOMAIN][CONFIG].get(CONF_USE_WEBHOOK)
    if use_webhook is not None and use_webhook != entry.options[CONF_USE_WEBHOOK]:
        new_options = entry.options.copy()
        new_options |= {CONF_USE_WEBHOOK: use_webhook}
        hass.config_entries.async_update_entry(entry, options=new_options)

    client = ConfigEntryWithingsApi(
        hass=hass,
        config_entry=entry,
        implementation=await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        ),
    )

    coordinator: BaseWithingsDataUpdateCoordinator
    if entry.options[CONF_USE_WEBHOOK]:
        webhook_coordinator = WebhookWithingsDataUpdateCoordinator(hass, client)

        @callback
        def async_call_later_callback(now) -> None:
            hass.async_create_task(webhook_coordinator.async_subscribe_webhooks())

        entry.async_on_unload(async_call_later(hass, 1, async_call_later_callback))
        webhook.async_register(
            hass,
            DOMAIN,
            "Withings notify",
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(webhook_coordinator),
        )
        coordinator = webhook_coordinator
    else:
        coordinator = PollingWithingsDataUpdateCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    if entry.options[CONF_USE_WEBHOOK]:
        async_unregister_webhook(hass, entry.data[CONF_WEBHOOK_ID])

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def json_message_response(message: str, message_code: int) -> Response:
    """Produce common json output."""
    return HomeAssistantView.json({"message": message, "code": message_code})


def get_webhook_handler(
    coordinator: WebhookWithingsDataUpdateCoordinator,
) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
    """Return webhook handler."""

    async def async_webhook_handler(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        # Handle http head calls to the path.
        # When creating a notify subscription, Withings will check that the endpoint is running by sending a HEAD request.
        if request.method.upper() == "HEAD":
            return Response()

        if request.method.upper() != "POST":
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
