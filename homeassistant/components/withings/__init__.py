"""Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
from __future__ import annotations

import asyncio

from aiohttp.web import Request, Response
import voluptuous as vol
from withings_api.common import NotifyAppli

from homeassistant.components import webhook
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from . import const
from .common import (
    async_get_data_manager,
    async_remove_data_manager,
    get_data_manager_by_webhook_id,
    json_message_response,
)
from .const import CONF_USE_WEBHOOK, CONFIG, LOGGER

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
                    vol.Optional(const.CONF_USE_WEBHOOK, default=False): cv.boolean,
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
    use_webhook = hass.data[DOMAIN][CONFIG][CONF_USE_WEBHOOK]
    if use_webhook is not None and use_webhook != entry.options[CONF_USE_WEBHOOK]:
        new_options = entry.options.copy()
        new_options |= {CONF_USE_WEBHOOK: use_webhook}
        hass.config_entries.async_update_entry(entry, options=new_options)

    data_manager = await async_get_data_manager(hass, entry)

    LOGGER.debug("Confirming %s is authenticated to withings", entry.title)
    await data_manager.poll_data_update_coordinator.async_config_entry_first_refresh()

    webhook.async_register(
        hass,
        const.DOMAIN,
        "Withings notify",
        data_manager.webhook_config.id,
        async_webhook_handler,
    )

    # Perform first webhook subscription check.
    if data_manager.webhook_config.enabled:
        data_manager.async_start_polling_webhook_subscriptions()

        @callback
        def async_call_later_callback(now) -> None:
            hass.async_create_task(
                data_manager.subscription_update_coordinator.async_refresh()
            )

        # Start subscription check in the background, outside this component's setup.
        entry.async_on_unload(async_call_later(hass, 1, async_call_later_callback))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    data_manager = await async_get_data_manager(hass, entry)
    data_manager.async_stop_polling_webhook_subscriptions()

    async_unregister_webhook(hass, data_manager.webhook_config.id)

    await asyncio.gather(
        data_manager.async_unsubscribe_webhook(),
        hass.config_entries.async_unload_platforms(entry, PLATFORMS),
    )

    async_remove_data_manager(hass, entry)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_webhook_handler(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response | None:
    """Handle webhooks calls."""
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
        return json_message_response("Parameter appli not provided", message_code=20)

    try:
        appli = NotifyAppli(int(params.getone("appli")))  # type: ignore[arg-type]
    except ValueError:
        return json_message_response("Invalid appli provided", message_code=21)

    data_manager = get_data_manager_by_webhook_id(hass, webhook_id)
    if not data_manager:
        LOGGER.error(
            (
                "Webhook id %s not handled by data manager. This is a bug and should be"
                " reported"
            ),
            webhook_id,
        )
        return json_message_response("User not found", message_code=1)

    # Run this in the background and return immediately.
    hass.async_create_task(data_manager.async_webhook_data_updated(appli))

    return json_message_response("Success", message_code=0)
