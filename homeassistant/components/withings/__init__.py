"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/withings/
"""
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers import config_validation as cv

from . import config_flow, const
from .sensor import WITHINGS_MEASUREMENTS_MAP

DOMAIN = const.DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
            vol.Schema({
                vol.Required(const.CLIENT_ID): vol.All(
                    cv.string, vol.Length(min=1)
                ),
                vol.Required(const.CLIENT_SECRET): vol.All(
                    cv.string, vol.Length(min=1)
                ),
                vol.Optional(const.BASE_URL): cv.url,
                vol.Required(const.PROFILES): vol.All(
                    cv.ensure_list,
                    vol.Unique(),
                    vol.Length(min=1),
                    [vol.All(
                        cv.string,
                        vol.Length(min=1)
                    )]
                ),
                vol.Optional(
                    const.MEASURES,
                    default=list(WITHINGS_MEASUREMENTS_MAP)
                ): vol.All(
                    cv.ensure_list,
                    vol.Unique(),
                    vol.Length(min=1),
                    [vol.All(
                        cv.string,
                        vol.In(list(WITHINGS_MEASUREMENTS_MAP))
                    )]
                ),
            })
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the Withings component."""
    conf = config.get(DOMAIN)
    if not conf:
        return True

    hass.data[DOMAIN] = {
        const.CONFIG: conf
    }

    base_url = conf.get(
        const.BASE_URL,
        hass.config.api.base_url
    ).rstrip('/')

    # We don't pull default values from conf because the config
    # schema would have validated it for us.
    for profile in conf.get(const.PROFILES):
        config_flow.register_flow_implementation(
            hass,
            conf.get(const.CLIENT_ID),
            conf.get(const.CLIENT_SECRET),
            base_url,
            profile
        )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': const.SOURCE_USER},
            data={}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Withings from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            entry,
            'sensor'
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Withings config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(
            entry,
            'sensor'
        )
    )

    return True
