"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
)
from homeassistant.core import callback
from homeassistant.helpers import discovery

REQUIREMENTS = ['plumlightpad==0.0.9']

DOMAIN = 'plum_lightpad'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Setup the Plum Lightpad component."""
    from plumlightpad import Plum

    conf = config[DOMAIN]
    plum = Plum(conf.get(CONF_USERNAME), conf.get(CONF_PASSWORD))

    hass.data['plum'] = plum

    @callback
    def cleanup(event):
        """Clean up resources."""
        print("Mr. Clean Spic and Span")
        # plum.cleanup()
        # shut down listeners, ports, etc.

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    discovery.load_platform(hass, 'light', DOMAIN, None, conf)
    discovery.load_platform(hass, 'sensor', DOMAIN, None, conf)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, None, conf)

    hass.add_job(plum.discover(hass.loop))

    return True
