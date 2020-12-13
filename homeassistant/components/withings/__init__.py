"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
import asyncio
from typing import Optional, cast

from aiohttp.web import Request, Response
import voluptuous as vol
from withings_api import WithingsAuth
from withings_api.common import NotifyAppli, enum_or_raise

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import config_flow
from .common import (
    _LOGGER,
    WithingsLocalOAuth2Implementation,
    async_get_data_manager,
    async_init_data_manager,
    async_register_webhook_config,
    async_remove_data_manager,
    async_unregister_webhook_config,
    get_data_manager_by_webhook_id,
    init_config_entry_data,
    json_message_response,
    remove_config_entry_data,
)
from .const import (
    CONF_PROFILES,
    CONF_USE_WEBHOOK,
    CONFIG,
    CONFIG_ENTRY_DATA,
    DOMAIN,
    URL_ARG_APPLI,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_PROFILES),
            cv.deprecated(CONF_USE_WEBHOOK, invalidation_version="0.119"),
            vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): vol.All(cv.string, vol.Length(min=1)),
                    vol.Required(CONF_CLIENT_SECRET): vol.All(
                        cv.string, vol.Length(min=1)
                    ),
                    vol.Optional(CONF_USE_WEBHOOK, default=False): cv.boolean,
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
    conf = config.get(DOMAIN, {})
    if not conf:
        return True

    # Make the config available to the oauth2 config flow.
    hass.data[DOMAIN] = {CONFIG: conf, CONFIG_ENTRY_DATA: {}}

    # Setup the oauth2 config flow.
    config_flow.WithingsFlowHandler.async_register_implementation(
        hass,
        WithingsLocalOAuth2Implementation(
            hass,
            DOMAIN,
            conf[CONF_CLIENT_ID],
            conf[CONF_CLIENT_SECRET],
            f"{WithingsAuth.URL}/{WithingsAuth.PATH_AUTHORIZE}",
            f"{WithingsAuth.URL}/{WithingsAuth.PATH_TOKEN}",
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Withings from a config entry."""
    _LOGGER.debug("Loading withings config entry.")
    init_config_entry_data(hass, entry)
    config_updates = {}

    # Add a unique id if it's an older config entry.
    if entry.unique_id != entry.data["token"]["userid"] or not isinstance(
        entry.unique_id, str
    ):
        config_updates["unique_id"] = str(entry.data["token"]["userid"])

    # Enable webhook by default if not already set and there is an active subscription.
    if (
        CONF_USE_WEBHOOK not in entry.options
        and hass.components.cloud.async_active_subscription()
    ):
        config_updates["options"] = {**entry.options, **{CONF_USE_WEBHOOK: True}}

    if config_updates:
        hass.config_entries.async_update_entry(entry, **config_updates)

    webhook_config = await async_register_webhook_config(
        hass, entry, async_webhook_handler
    )
    data_manager = await async_init_data_manager(hass, entry, webhook_config)

    _LOGGER.debug("Confirming %s is authenticated to withings", data_manager.profile)
    await data_manager.poll_data_update_coordinator.async_refresh()
    if not data_manager.poll_data_update_coordinator.last_update_success:
        raise ConfigEntryNotReady()

    data_manager.async_start_polling_webhook_subscriptions()

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, BINARY_SENSOR_DOMAIN)
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )
    hass.async_create_task(data_manager.async_subscribe_webhook())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    _LOGGER.debug("Unloading withings config entry.")

    data_manager = await async_get_data_manager(hass, entry)
    data_manager.async_stop_polling_webhook_subscriptions()

    await asyncio.gather(
        async_unregister_webhook_config(hass, data_manager.webhook_config),
        data_manager.async_unsubscribe_webhook(),
        hass.config_entries.async_forward_entry_unload(entry, BINARY_SENSOR_DOMAIN),
        hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN),
    )

    async_remove_data_manager(hass, entry)
    remove_config_entry_data(hass, entry)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Remove Withings config entry."""


async def async_webhook_handler(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Optional[Response]:
    """Handle webhooks calls."""
    # Handle http head calls to the path.
    # When creating a notify subscription, Withings will check that the endpoint is running by sending a HEAD request.
    if request.method.upper() == "HEAD":
        return Response()

    if request.method.upper() != "POST":
        return json_message_response("Invalid method", message_code=2)

    params = await request.post()

    if URL_ARG_APPLI not in params:
        return json_message_response(
            f"Parameter {URL_ARG_APPLI} not provided", message_code=20
        )

    try:
        appli = cast(
            NotifyAppli, enum_or_raise(int(params.getone(URL_ARG_APPLI)), NotifyAppli)
        )
    except ValueError:
        return json_message_response(
            f"Invalid {URL_ARG_APPLI} provided", message_code=21
        )

    data_manager = get_data_manager_by_webhook_id(hass, webhook_id)
    if not data_manager:
        _LOGGER.error(
            "Webhook id %s not handled by data manager. This is a bug and should be reported",
            webhook_id,
        )
        return json_message_response("User not found", message_code=1)

    # Run this in the background and return immediately.
    hass.async_create_task(data_manager.async_webhook_data_updated(appli))

    return json_message_response("Success", message_code=0)
