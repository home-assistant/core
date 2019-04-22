"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/withings/
"""
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.components.withings import (
    config_flow,  # noqa  pylint_disable=unused-import
    const
)
from homeassistant.components.withings.common import (
    _LOGGER,
    WithingsDataManager
)

DOMAIN = const.DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
            vol.Schema({
                vol.Required(const.CLIENT_ID): cv.string,
                vol.Required(const.CLIENT_SECRET): cv.string,
                vol.Optional(const.BASE_URL): cv.string,
                vol.Required(const.PROFILES): [cv.string],
            })
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Withings component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    base_url = hass.config.api.base_url.rstrip('/')
    if const.BASE_URL in conf and conf[const.BASE_URL] is not None:
        base_url = conf[const.BASE_URL].rstrip('/')

    for profile in conf[const.PROFILES]:
        config_flow.register_flow_implementation(
            hass,
            conf[const.CLIENT_ID],
            conf[const.CLIENT_SECRET],
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


async def async_setup_entry(hass, entry):
    """Set up Withings from a config entry."""
    _LOGGER.debug("Forwarding config entry setup for '%s' to the sensor platform.", entry.data[const.PROFILE])
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry,
        'sensor'
    ))
    return True
