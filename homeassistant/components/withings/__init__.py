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
from .common import _LOGGER, ensure_unique_list
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
                    ensure_unique_list,
                    vol.Length(min=1),
                    [vol.All(
                        cv.string,
                        vol.Length(min=1)
                    )]
                ),
                vol.Optional(
                    const.MEASURES,
                    default=list(WITHINGS_MEASUREMENTS_MAP.keys())
                ): vol.All(
                    cv.ensure_list,
                    ensure_unique_list,
                    vol.Length(min=1),
                    [vol.All(
                        cv.string,
                        vol.In(list(WITHINGS_MEASUREMENTS_MAP.keys()))
                    )]
                ),
            })
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the Withings component."""
    conf = config.get(DOMAIN, None)
    if not conf:
        _LOGGER.debug("No withing config was provided.")
        return True

    _LOGGER.debug("Saving component config for later.")
    hass.data[DOMAIN] = {
        const.CONFIG: conf
    }

    _LOGGER.debug("Determining the base url to use for callbacks.")
    base_url = conf.get(
        const.BASE_URL,
        hass.config.api.base_url
    ).rstrip('/')

    _LOGGER.debug("Setting up configuration flow data.")
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

    _LOGGER.debug("Initializing configuration flow.")
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
    _LOGGER.debug(
        "Forwarding setup config entry for '%s' to the sensor platform.",
        entry.data[const.PROFILE]
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            entry,
            'sensor'
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Withings config entry."""
    _LOGGER.debug(
        "Forwarding unload of config entry for '%s' to the sensor platform.",
        entry.data[const.PROFILE]
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(
            entry,
            'sensor'
        )
    )

    return True
