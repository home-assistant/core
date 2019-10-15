"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT, SOURCE_USER
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers import config_validation as cv

from . import config_flow, const
from .common import _LOGGER, get_data_manager, NotAuthenticatedError

DOMAIN = const.DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(const.CLIENT_ID): vol.All(cv.string, vol.Length(min=1)),
                vol.Required(const.CLIENT_SECRET): vol.All(
                    cv.string, vol.Length(min=1)
                ),
                vol.Optional(const.BASE_URL): cv.url,
                vol.Required(const.PROFILES): vol.All(
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


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the Withings component."""
    conf = config.get(DOMAIN)
    if not conf:
        return True

    hass.data[DOMAIN] = {const.CONFIG: conf}

    base_url = conf.get(const.BASE_URL, hass.config.api.base_url).rstrip("/")

    hass.http.register_view(config_flow.WithingsAuthCallbackView)

    config_flow.register_flow_implementation(
        hass,
        conf[const.CLIENT_ID],
        conf[const.CLIENT_SECRET],
        base_url,
        conf[const.PROFILES],
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Withings from a config entry."""
    data_manager = get_data_manager(hass, entry)

    _LOGGER.debug("Confirming we're authenticated")
    try:
        await data_manager.check_authenticated()
    except NotAuthenticatedError:
        # Trigger new config flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                const.DOMAIN,
                context={"source": SOURCE_USER, const.PROFILE: data_manager.profile},
                data={},
            )
        )
        return False

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Withings config entry."""
    await hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(entry, "sensor")
    )

    return True
