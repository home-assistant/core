"""
Support for device connected via Lightwave WiFi-link hub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lightwave/
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_LIGHTS, CONF_NAME,
                                 CONF_SWITCHES)
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['lightwave==0.17']
LIGHTWAVE_LINK = 'lightwave_link'
DOMAIN = 'lightwave'
SERVICE_REGISTER = 'lightwave_registration'
SERVICE_DEREGISTER = 'lightwave_deregistration'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema(
        cv.has_at_least_one_key(CONF_LIGHTS, CONF_SWITCHES), {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_LIGHTS, default={}): {
                cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string}),
            },
            vol.Optional(CONF_SWITCHES, default={}): {
                cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string}),
            }
        })
}, extra=vol.ALLOW_EXTRA)

# Currently no attributes but it might change later
LIGHTWAVE_REGISTRATION_SCHEMA = vol.Schema({})
LIGHTWAVE_DEREGISTRATION_SCHEMA = vol.Schema({})


async def async_setup(hass, config):
    """Try to start embedded Lightwave broker."""
    from lightwave.lightwave import LWLink

    host = config[DOMAIN][CONF_HOST]
    hass.data[LIGHTWAVE_LINK] = LWLink(host)

    """Provide service to register with Lightwave Wifi Link"""
    async def async_registration_service_handler(service):
        lwlink = hass.data[LIGHTWAVE_LINK]
        lwlink.register()

    """Provide service to deregister with Lightwave Wifi Link"""
    async def async_deregistration_service_handler(service):
        lwlink = hass.data[LIGHTWAVE_LINK]
        lwlink.deregister_all()

    lights = config[DOMAIN][CONF_LIGHTS]
    if lights:
        hass.async_create_task(async_load_platform(
            hass, 'light', DOMAIN, lights, config))

    switches = config[DOMAIN][CONF_SWITCHES]
    if switches:
        hass.async_create_task(async_load_platform(
            hass, 'switch', DOMAIN, switches, config))

    hass.services.async_register(
        DOMAIN, SERVICE_REGISTER, async_registration_service_handler,
        schema=LIGHTWAVE_REGISTRATION_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_DEREGISTER, async_deregistration_service_handler,
        schema=LIGHTWAVE_DEREGISTRATION_SCHEMA)

    return True
