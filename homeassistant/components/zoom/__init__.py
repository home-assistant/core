"""The Zoom integration."""
from logging import getLogger

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .api import ZoomAPI
from .common import ZoomOAuth2Implementation, ZoomWebhookRequestView
from .config_flow import ZoomOAuth2FlowHandler
from .const import (
    API,
    CONF_VERIFICATION_TOKEN,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    UNSUB,
    ZOOM_SCHEMA,
)

_LOGGER = getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: ZOOM_SCHEMA}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the Zoom component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    ZoomOAuth2FlowHandler.async_register_implementation(
        hass,
        ZoomOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
            config[DOMAIN][CONF_VERIFICATION_TOKEN],
        ),
    )
    hass.data[DOMAIN][SOURCE_IMPORT] = True

    return True


@callback
async def _async_send_update_options_signal(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Send update event when Zoom config entry is updated."""
    async_dispatcher_send(hass, config_entry.entry_id, config_entry)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Zoom from a config entry."""
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except ValueError:
        implementation = ZoomOAuth2Implementation(
            hass,
            DOMAIN,
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
            entry.data.get(CONF_VERIFICATION_TOKEN),
        )
        ZoomOAuth2FlowHandler.async_register_implementation(hass, implementation)

    api = ZoomAPI(config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation))

    unsub = entry.add_update_listener(_async_send_update_options_signal)
    hass.data[DOMAIN][entry.entry_id].update(
        {
            API: api,
            UNSUB: [unsub],
        }
    )

    # Register view
    hass.http.register_view(
        ZoomWebhookRequestView(entry.data.get(CONF_VERIFICATION_TOKEN))
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    for unsub in hass.data[DOMAIN][config_entry.entry_id][UNSUB]:
        unsub()

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True
