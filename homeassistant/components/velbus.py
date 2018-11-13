"""
Support for Velbus platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/velbus/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_PORT
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-velbus==2.0.21']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'velbus'


VELBUS_MESSAGE = 'velbus.message'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Velbus platform."""
    import velbus
    port = config[DOMAIN].get(CONF_PORT)
    controller = velbus.Controller(port)

    hass.data[DOMAIN] = controller

    def stop_velbus(event):
        """Disconnect from serial port."""
        _LOGGER.debug("Shutting down ")
        controller.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_velbus)

    def callback():
        modules = controller.get_modules()
        discovery_info = {
            'switch': [],
            'binary_sensor': [],
            'sensor': []
        }
        for module in modules:
            for channel in range(1, module.number_of_channels() + 1):
                for category in discovery_info:
                    if category in module.get_categories(channel):
                        discovery_info[category].append((
                            module.get_module_address(),
                            channel
                        ))
        load_platform(hass, 'switch', DOMAIN,
                      discovery_info['switch'], config)
        load_platform(hass, 'binary_sensor', DOMAIN,
                      discovery_info['binary_sensor'], config)
        load_platform(hass, 'sensor', DOMAIN,
                      discovery_info['sensor'], config)

    controller.scan(callback)

    return True


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    def __init__(self, module, channel):
        """Initialize a Velbus entity."""
        self._module = module
        self._channel = channel

    @property
    def unique_id(self):
        """Get unique ID."""
        serial = 0
        if self._module.serial == 0:
            serial = self._module.get_module_address()
        else:
            serial = self._module.serial
        return "{}-{}".format(serial, self._channel)

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._module.get_name(self._channel)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_added_to_hass(self):
        """Add listener for state changes."""
        self._module.on_status_update(self._channel, self._on_update)

    def _on_update(self, state):
        self.schedule_update_ha_state()
