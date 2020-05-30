"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
import voluptuous as vol
from withings_api import WithingsAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import config_flow
from .common import _LOGGER, NotAuthenticatedError, get_data_manager
from .const import CONF_PROFILES, CONFIG, CREDENTIALS, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): vol.All(cv.string, vol.Length(min=1)),
                vol.Required(CONF_CLIENT_SECRET): vol.All(cv.string, vol.Length(min=1)),
                vol.Required(CONF_PROFILES): vol.All(
                    cv.ensure_list,
                    vol.Unique(),
                    vol.Length(min=1),
                    [vol.All(cv.string, vol.Length(min=1))],
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Withings component."""
    conf = config.get(DOMAIN, {})
    if not conf:
        return True

    hass.data[DOMAIN] = {CONFIG: conf}

    config_flow.WithingsFlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            conf[CONF_CLIENT_ID],
            conf[CONF_CLIENT_SECRET],
            f"{WithingsAuth.URL}/oauth2_user/authorize2",
            f"{WithingsAuth.URL}/oauth2/token",
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Withings from a config entry."""
    # Upgrading existing token information to hass managed tokens.
    if "auth_implementation" not in entry.data:
        _LOGGER.debug("Upgrading existing config entry")
        data = entry.data
        creds = data.get(CREDENTIALS, {})
        hass.config_entries.async_update_entry(
            entry,
            data={
                "auth_implementation": DOMAIN,
                "implementation": DOMAIN,
                "profile": data.get("profile"),
                "token": {
                    "access_token": creds.get("access_token"),
                    "refresh_token": creds.get("refresh_token"),
                    "expires_at": int(creds.get("token_expiry")),
                    "type": creds.get("token_type"),
                    "userid": creds.get("userid") or creds.get("user_id"),
                },
            },
        )

    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    data_manager = get_data_manager(hass, entry, implementation)

    _LOGGER.debug("Confirming we're authenticated")
    try:
        await data_manager.check_authenticated()
    except NotAuthenticatedError:
        _LOGGER.error(
            "Withings auth tokens exired for profile %s, remove and re-add the integration",
            data_manager.profile,
        )
        return False

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
